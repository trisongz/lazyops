"""
Generic helpers for apis when working with multi workers
"""

from lazyops.imports._psutil import resolve_psutil

resolve_psutil(True)

import os
import psutil
from typing import List, Optional
from lazyops.types import BaseModel, lazyproperty


class NodeProcess(BaseModel):
    pid: int # Current Worker PID
    name: str # Process Name
    exe: str # Command Line
    cmdline: List[str]

    is_worker: Optional[bool] = None
    has_workers: Optional[bool] = None

    parent: Optional[psutil.Process] = None
    linked: Optional[List[psutil.Process]] = []

    # Context vars
    runtime: Optional[str] = None
    entrypoint: Optional[str] = None
    exact_match: Optional[bool] = None
    worker_entrypoint: Optional[str] = None


    @lazyproperty
    def parent_pid(self) -> Optional[int]:
        """
        Parent PID
        """
        return self.parent.pid if self.parent else None
    
    @lazyproperty
    def parent_cmdline(self) -> Optional[List[str]]:
        """
        Parent Command Line
        """
        return self.parent.cmdline() if self.parent else None
    
    @lazyproperty
    def parent_exe(self) -> Optional[str]:
        """
        Parent Executable
        """
        return self.parent.exe() if self.parent else None

    @lazyproperty
    def linked_pids(self) -> Optional[List[int]]:
        """
        Linked PID's
        """
        return [p.pid for p in self.linked] if self.linked else None

    @lazyproperty
    def is_parent(self) -> bool:
        """
        If the parent process is none, we assume it is the current
        process. This is the case when running in a single worker
        """
        return (
            self.pid == self.parent_pid \
            if self.parent_pid is not None else True
        )

    @lazyproperty
    def is_multiprocess(self) -> bool:
        """
        If the linked pids are empty, we assume it is a single
        process. This is the case when running in a single worker
        """
        return any('multiprocessing' in cmd for cmd in self.cmdline)

    @staticmethod
    def get_stripped_cmdline(
        cmdline: List[str],
        has_workers: bool = False,
    ) -> str:
        """
        Strips the current process from the cmdline
        and removes params that are not needed
        """
        cmd = ""
        for cmd_arg in cmdline:
            if 'pipe_handle' in cmd_arg:
                cmd_arg = cmd_arg.split(', pipe_handle', 1)[0] + ')'
                # will fix this later
                if has_workers and 'tracker_fd' in cmd_arg:
                    cmd_arg = '(' + cmd_arg.split('(tracker_fd', 1)[0] + ')'
            cmd += f'|{cmd_arg}' 
        return cmd

    @lazyproperty
    def stripped_cmdline(self) -> List[str]:
        """
        Strips the current process from the cmdline
        and removes params that are not needed
        """
        return self.get_stripped_cmdline(self.cmdline)
        # return self.get_stripped_cmdline(self.cmdline, has_workers = self.has_workers)
    
    @lazyproperty
    def total_processes(self) -> int:
        """
        Returns the total number of processes
        """
        return len(self.linked_pids) + 1 if self.linked_pids else 1
    
    @lazyproperty
    def sorted_linked_pids(self) -> List[int]:
        """
        Returns the sorted linked pids
        """
        if not self.linked_pids: return []
        pids = list(self.linked_pids)
        if not self.is_parent:
            pids.append(self.pid)
        if self.parent_pid and self.parent_pid in pids:
            pids.remove(self.parent_pid)
        return sorted(pids, key=int)

    # @lazyproperty
    @property
    def leader_pid(self) -> Optional[int]:
        """
        Returns the leader pid
        """
        if self.is_worker: return self.sorted_linked_pids[1] if len(self.sorted_linked_pids) > 1 else None
        return self.parent_pid if self.is_parent else self.sorted_linked_pids[0]
    
    # @lazyproperty
    @property
    def is_leader(self) -> bool:
        """
        If the current process is the leader

        detect the first worker pid by numerical order
        """
        return True if self.is_parent else self.leader_pid == self.pid
    
    
    @classmethod
    def get_process(
        cls,
        pid: Optional[int] = None,
        runtime: Optional[str] = "uvicorn",
        entrypoint: Optional[str] = "main:app",
        exact_match: Optional[bool] = False,
        is_worker: Optional[bool] = False,
        worker_entrypoint: Optional[str] = None,
        has_workers: Optional[bool] = False,
    ) -> 'NodeProcess':
        """
        Utility Function to get the current process information
        of the current node / worker

        can probably improve the logic but it works for now.
        """
        node_pid = pid or os.getpid()
        node_process = psutil.Process(node_pid)

        process = cls(
            pid = node_pid,
            name = node_process.name(),
            exe = node_process.exe(),
            cmdline = node_process.cmdline(),
            has_workers = has_workers,
            is_worker = is_worker,

            # Context vars
            runtime = runtime,
            entrypoint = entrypoint,
            exact_match = exact_match,
            worker_entrypoint = worker_entrypoint,
        )

        for p in psutil.process_iter(attrs=["pid", "name", "exe", "cmdline"]):
            if p.info["pid"] == node_pid:
                continue

            # Check that the process name is identical to the node
            if p.info['exe'] != process.exe:
                continue

            if not is_worker and \
                any(runtime in cmd_arg for cmd_arg in p.info["cmdline"]) and \
                    any((entrypoint == cmd_arg if exact_match else entrypoint in cmd_arg) for cmd_arg in p.info["cmdline"]):
                
                process.linked.append(p)
                process.parent = p
                continue


            if (
                is_worker
                and worker_entrypoint
                and all(runtime not in cmd_arg for cmd_arg in p.info["cmdline"])
                and any(
                    (
                        worker_entrypoint == cmd_arg
                        if exact_match
                        else worker_entrypoint in cmd_arg
                    )
                    for cmd_arg in p.info["cmdline"]
                )
                and not process.parent
            ):
                process.parent = p
                continue


            # if process.is_multiprocess and process.stripped_cmdline == cls.get_stripped_cmdline(p.info["cmdline"], has_workers = has_workers):
            if process.is_multiprocess and process.stripped_cmdline == cls.get_stripped_cmdline(p.info["cmdline"]):
                process.linked.append(p)
                continue
        
        return process
    
    def reconfigure(self):
        """
        Reconfigures the current process
        """
        self = self.get_process(
            pid = self.pid,
            runtime = self.runtime,
            entrypoint = self.entrypoint,
            exact_match = self.exact_match,
            is_worker = self.is_worker,
            worker_entrypoint = self.worker_entrypoint,
        )
