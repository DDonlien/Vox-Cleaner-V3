"""Isolated Blender processes; all access to the live scene stays on its main thread."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

import bpy
from bpy.app.handlers import persistent

ACTIVE = None
LAST_REPORT = None


def settings_dict(settings):
    result = {}
    for prop in settings.bl_rna.properties:
        if prop.identifier == 'rna_type' or prop.is_readonly:
            continue
        value = getattr(settings, prop.identifier)
        result[prop.identifier] = list(value) if getattr(prop, 'is_array', False) else value
    return result


def safe_names(names):
    """Stable, portable filenames, including case-insensitive filesystem collisions."""
    used, result = set(), {}
    for name in names:
        base = bpy.path.clean_name(name).strip('. ') or 'Model'
        base = base.encode('utf-8')[:160].decode('utf-8', errors='ignore')
        if base.upper() in {'CON', 'PRN', 'AUX', 'NUL',
                            *(f'COM{i}' for i in range(1, 10)),
                            *(f'LPT{i}' for i in range(1, 10))}:
            base = '_' + base
        candidate, index = base, 1
        while candidate.casefold() in used:
            candidate = f'{base}_{index}'
            index += 1
        used.add(candidate.casefold())
        result[name] = candidate
    return result


def worker_budget(count, requested, snapshot_bytes):
    cores = max(1, (os.cpu_count() or 1) - 1)
    workers = min(count, requested or 8, cores)
    # Reserve half the system memory; every process has a Blender and mesh copy.
    try:
        if sys_platform() == 'darwin':
            ram = int(subprocess.check_output(['sysctl', '-n', 'hw.memsize']))
        else:
            ram = os.sysconf('SC_PHYS_PAGES') * os.sysconf('SC_PAGE_SIZE')
        estimate = 768 * 1024**2 + snapshot_bytes * 6
        workers = min(workers, max(1, int(ram * 0.5 / estimate)))
    except (AttributeError, ValueError, OSError, subprocess.SubprocessError):
        workers = min(workers, 2)
    workers = max(1, workers)
    return workers, max(1, cores // workers)


def sys_platform():
    import sys
    return sys.platform


class BatchRun:
    def __init__(self, context, operation, objects, addon):
        self.scene = context.scene
        self.workspace = context.workspace
        self.operation = operation
        self.addon = addon
        self.objects = {obj.name: obj for obj in objects}
        self.original_meshes = {obj.name: obj.data for obj in objects}
        self.settings = settings_dict(context.scene.vox_tool)
        if operation != 'clean':
            # Resolve Blender's // paths against the user's file, before workers
            # start from their own factory scene and temporary library.
            self.settings['ExportLocation'] = os.path.realpath(
                bpy.path.abspath(self.settings['ExportLocation']))
        self.directory = Path(tempfile.mkdtemp(prefix='vox-cleaner-'))
        self.pending, self.running, self.completed, self.errors = [], [], [], []
        self.peak_workers = 0
        self.cancelled = False
        self.closed = False
        try:
            snapshot = self.directory / 'input.blend'
            bpy.data.libraries.write(str(snapshot), set(objects), path_remap='ABSOLUTE')
            self.workers, self.threads = worker_budget(
                len(objects), self.settings['BatchWorkers'], snapshot.stat().st_size)
            names = safe_names(self.objects)
            for i, obj in enumerate(objects):
                job = dict(operation=operation, object=obj.name, settings=self.settings,
                           input=str(snapshot), output=str(self.directory / f'{i}.blend'),
                           status=str(self.directory / f'{i}.status.json'),
                           export_name=names[obj.name], threads=self.threads,
                           addon=str(Path(addon.__file__).parent),
                           log=str(self.directory / f'{i}.log'))
                path = self.directory / f'{i}.job.json'
                path.write_text(json.dumps(job), encoding='utf-8')
                job['path'] = str(path)
                self.pending.append(job)
        except Exception:
            shutil.rmtree(self.directory)
            raise

    def launch(self, job):
        log = open(job['log'], 'w', encoding='utf-8')
        env = os.environ.copy()
        for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
            env[name] = str(self.threads)
        try:
            job['process'] = subprocess.Popen([
                bpy.app.binary_path, '--background', '--factory-startup',
                '--disable-autoexec', '--threads', str(self.threads),
                '--python-exit-code', '1', '--python',
                str(Path(__file__).with_name('batch_worker.py')), '--', job['path']],
                stdout=log, stderr=subprocess.STDOUT, env=env)
        finally:
            log.close()
        self.running.append(job)
        self.peak_workers = max(self.peak_workers, len(self.running))

    def apply_clean(self, job, result):
        obj = self.objects[job['object']]
        if (obj.name not in self.scene.objects or
                obj.data != self.original_meshes[job['object']]):
            raise RuntimeError('Target object changed while cleaning; result was not applied')
        with bpy.data.libraries.load(job['output'], link=False) as (source, target):
            target.meshes = [result['mesh']]
        mesh = target.meshes[0]
        if mesh is None or not mesh.polygons:
            raise RuntimeError('Worker returned no usable mesh')
        if self.settings['CreateBackup']:
            backup = obj.copy()
            backup.data = obj.data.copy()
            backup.name = self.addon.VoxMethods.NextNamePlease(obj.name)
            if self.settings['OrganiseBackups']:
                collection = bpy.data.collections.get('Vox Cleaner Backups')
                if collection is None:
                    collection = bpy.data.collections.new('Vox Cleaner Backups')
                if collection.name not in self.scene.collection.children:
                    self.scene.collection.children.link(collection)
                collection.objects.link(backup)
            else:
                (obj.users_collection[0] if obj.users_collection else self.scene.collection).objects.link(backup)
            backup.hide_render = True
            backup.hide_set(True)
        obj.data = mesh

    def tick(self):
        for job in list(self.running):
            code = job['process'].poll()
            if code is None:
                continue
            self.running.remove(job)
            try:
                result = json.loads(Path(job['status']).read_text(encoding='utf-8'))
                if code or not result.get('ok'):
                    raise RuntimeError(result.get('error', f'Blender exited with code {code}'))
                if self.operation == 'clean':
                    self.apply_clean(job, result)
                self.completed.append({'object': job['object'], **result})
            except Exception as error:
                self.errors.append(f"{job['object']}: {error}")
                print(f"Vox Cleaner batch error: {self.errors[-1]}")
                print(Path(job['log']).read_text(encoding='utf-8', errors='replace')[-6000:])
        while self.pending and len(self.running) < self.workers:
            job = self.pending.pop(0)
            try:
                self.launch(job)
            except Exception as error:
                self.errors.append(f"{job['object']}: {error}")
        return not self.pending and not self.running

    def stop(self):
        self.cancelled = True
        self.pending.clear()
        for job in self.running:
            job['process'].terminate()
        for job in self.running:
            try:
                job['process'].wait(timeout=3)
            except subprocess.TimeoutExpired:
                job['process'].kill()
                job['process'].wait()
        self.running.clear()

    def close(self):
        global ACTIVE, LAST_REPORT
        if self.closed:
            return
        self.closed = True
        LAST_REPORT = dict(operation=self.operation, completed=self.completed,
                           errors=self.errors, cancelled=self.cancelled,
                           peak_workers=self.peak_workers, threads=self.threads)
        # Keep logs of failed jobs, but discard large snapshots and output libraries.
        if self.errors:
            for path in self.directory.glob('*.blend*'):
                path.unlink()
            LAST_REPORT['logs'] = str(self.directory)
        else:
            shutil.rmtree(self.directory)
        ACTIVE = None


class BatchOperator:
    """Mixin for the existing Clean / OBJ / FBX operators (no extra buttons)."""
    _timer = None
    _batch = None

    def start_batch(self, context, operation):
        global ACTIVE
        from . import VoxMethods
        import sys
        addon = sys.modules[__package__]
        if ACTIVE:
            self.report({'WARNING'}, 'A batch is already running')
            return {'CANCELLED'}
        try:
            if operation != 'clean':
                VoxMethods.TextureExport(context)
            ACTIVE = self._batch = BatchRun(context, operation, list(context.selected_objects), addon)
            context.window_manager.progress_begin(0, len(self._batch.objects))
            if bpy.app.background or context.window is None:
                while not self._batch.tick():
                    time.sleep(0.05)
                return self.finish_batch(context)
            self._timer = context.window_manager.event_timer_add(0.2, window=context.window)
            context.window_manager.modal_handler_add(self)
            self._batch.tick()
            self.report({'INFO'}, f'Batch started: {len(self._batch.objects)} objects, {self._batch.workers} workers. Esc to cancel.')
            return {'RUNNING_MODAL'}
        except Exception as error:
            if self._batch:
                self._batch.stop()
                self.finish_batch(context)
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}

    def modal(self, context, event):
        if ACTIVE is not self._batch or event.type == 'ESC':
            if self._batch:
                self._batch.stop()
            return self.finish_batch(context)
        if event.type == 'TIMER':
            try:
                done = self._batch.tick()
                count = len(self._batch.completed) + len(self._batch.errors)
                context.window_manager.progress_update(count)
                context.workspace.status_text_set(f'Vox Cleaner: {count}/{len(self._batch.objects)} objects — Esc to cancel')
                if done:
                    return self.finish_batch(context)
            except Exception as error:
                self._batch.errors.append(str(error))
                self._batch.stop()
                return self.finish_batch(context)
        # Prevent edits to the scene while its snapshot is being processed.
        return {'RUNNING_MODAL'}

    def finish_batch(self, context):
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        context.window_manager.progress_end()
        if context.workspace:
            context.workspace.status_text_set(None)
        run = self._batch
        if run is None:
            return {'CANCELLED'}
        count = len(run.completed)
        message = f'{count}/{len(run.objects)} objects {"cleaned" if run.operation == "clean" else "exported"}'
        if run.cancelled:
            message += '; cancelled (completed results kept)'
        if run.errors:
            message += f'; {len(run.errors)} failed: {run.errors[0]}'
        self.report({'WARNING'} if run.errors or run.cancelled else {'INFO'}, message)
        run.close()
        self._batch = None
        return {'FINISHED'} if count else {'CANCELLED'}


@persistent
def cancel_on_load(_):
    if ACTIVE:
        ACTIVE.stop()
        ACTIVE.close()
        bpy.context.window_manager.progress_end()
        if bpy.context.workspace:
            bpy.context.workspace.status_text_set(None)


def register():
    if cancel_on_load not in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.append(cancel_on_load)


def unregister():
    if ACTIVE:
        ACTIVE.stop()
        ACTIVE.close()
    if cancel_on_load in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.remove(cancel_on_load)
