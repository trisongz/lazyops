import sys
import datetime
import inspect
import pathlib
import jinja2
import hatchet_sdk
from importlib.metadata import version

here = pathlib.Path(__file__).parent.parent
patches_dir = here.joinpath('_patches')

j2 = jinja2.Environment(loader=jinja2.FileSystemLoader(patches_dir))

last_version = '0.32.0'

replacements = {
    'worker.py': {
        '__init__': [
    # (
    #     'config: ClientConfig = {},',
    #     "config: ClientConfig = {},\n\
    #     session: Optional['HatchetSession'] = None,\n\
    #     context_class: Type[Context] = Context,\n"
    # ),
    (
        'labels: dict[str, str | int] = {},',
        "labels: dict[str, str | int] = {},\n\
        session: Optional['HatchetSession'] = None,\n\
        context_class: Type[Context] = Context,\n"
    ),
    (
        'self.client = new_client_raw(config)', 
        "self.session = session\n\
        self.client = self.session.client if self.session else new_session(config)\n\
        self._loop: Optional[asyncio.AbstractEventLoop] = None\n\
        self._context_cls = context_class\n\
        self.main_task = None\n"
    )
        ],
        'handle_start_step_run': [
    (
        'context = Context(',
        'context = self._context_cls(',
    )
        ],
        'handle_start_group_key_run': [
    (
        'context = Context(',
        'context = self._context_cls(',
    ),
    (
        'except Exception as e:',
            'except Exception as e:\n\
                if "]:" in str(e) and "- 40" in str(e):\n\
                    logger.error(f"[{action.step_run_id} - {action.job_name}] Error in action: {e}")\n\
                    raise e',
        1
    )
        ],
        'async_wrapped_action_func': [
    (
        'except Exception as e:',
        'except Exception as e:\n\
            if "]:" in str(e) and "- 40" in str(e):\n\
                logger.error(f"[{action.step_run_id} - {action.job_name}] Error in action: {e}")\n\
                raise e'
    )
        ],
        'get_step_action_finished_event': [
    (
        'json.loads',
        'json_serializer.loads'
    ),
        ],
    #     '_async_start': [
    # (
    #     'self.loop = asyncio.get_running_loop()',
    #     'self.loop = asyncio.get_running_loop()\n\
    #     self.run_watcher_event()',
    #     # '# self.loop = asyncio.get_running_loop()',
    # )
    #     ]
    },
    'context.py': {
        '__init__': [
            (
                'json.loads',
                'json_serializer.loads'
            ),
            (
                'Action',
                "'Action'", 1
            ),
            (
                'DispatcherClientImpl',
                "'DispatcherClientImpl'", 1
            ),
            (
                'AdminClientImpl',
                "'AdminClientImpl'", 1
            ),
            (
                'EventClientImpl',
                "'EventClientImpl'", 1
            ),
            (
                'PooledWorkflowRunListener',
                "'PooledWorkflowRunListener'", 1
            ),
            (
                'RunEventListenerClient',
                "'RunEventListenerClient'", 1
            ),
            (
                'WorkerContext',
                "'WorkerContext'", 1
            )
        ],
    },

}


def patch_worker(
    version: str,
    timestamp: str,
    version_dir: pathlib.Path,
    version_id: float,
):
    """
    Patches the worker class to add the ability to handle start step run
    """
    worker = hatchet_sdk.worker.Worker
    patched_funcs = {}
    for name, patches in replacements['worker.py'].items():
        func_string = inspect.getsource(getattr(worker, name))
        for patch in patches:
            func_string = func_string.replace(*patch)
        patched_funcs[name] = func_string
    
    template = j2.get_template('worker.j2.py')
    output = template.render(new_funcs = patched_funcs, version = version, timestamp = timestamp, last_version = last_version)
    output_file = version_dir.joinpath('worker.py')
    output_file.write_text(output)

def patch_context(
    version: str,
    timestamp: str,
    version_dir: pathlib.Path,
    version_id: float,
):
    """
    Patches the context class to add the necessary methods
    """
    # context = hatchet_sdk.context.context.Context
    from hatchet_sdk.context.context import Context
    context = Context
    patched_funcs = {}
    for name, patches in replacements['context.py'].items():
        func_string = inspect.getsource(getattr(context, name))
        for patch in patches:
            func_string = func_string.replace(*patch)
        patched_funcs[name] = func_string
    
    template = j2.get_template('context.j2.py')
    output = template.render(new_funcs = patched_funcs, version = version, timestamp = timestamp, last_version = last_version)
    output_file = version_dir.joinpath('context.py')
    output_file.write_text(output)

def create_version_file(
    version: str,
    version_dir: pathlib.Path,
    version_id: float,
):
    """
    Creates the version file
    """
    template = j2.get_template('version.j2.py')
    output = template.render(version = version, last_version = last_version)
    output_file = version_dir.joinpath('version.py')
    output_file.write_text(output)

def create_init_file(
    version: str,
    version_dir: pathlib.Path,
    version_id: float,
) -> None:
    """
    Creates the init file
    """
    template = j2.get_template('ver_init.j2.py')
    output = template.render(version = version, last_version = last_version)
    output_file = version_dir.joinpath('__init__.py')
    output_file.write_text(output)

def create_current_file(
    version: str,
    version_dir: pathlib.Path,
    version_id: float,
) -> None:
    """
    Creates the current file
    """
    template = j2.get_template('current.j2.py')
    current_version_name = version_dir.name
    output = template.render(version = version, last_version = last_version, current_version_name = current_version_name)
    output_file = here.joinpath('current', '__init__.py')
    output_file.write_text(output)


def run_patches():
    ver = version('hatchet-sdk')
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ver_dir_name = f'v{ver.replace(".", "")}'
    ver_dir = here.joinpath(ver_dir_name)
    ver_dir.mkdir(exist_ok = True)
    ver_id = float(ver.split('.', 1)[1])
    patch_worker(ver, timestamp, ver_dir, ver_id)
    patch_context(ver, timestamp, ver_dir, ver_id)
    create_version_file(ver, ver_dir, ver_id)
    create_init_file(ver, ver_dir, ver_id)
    create_current_file(ver, ver_dir, ver_id)

if __name__ == '__main__':
    run_patches()

# patch_worker()
# patch_context()
