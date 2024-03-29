#!/usr/bin/env python3
"""
Abstract: Simple application hub, intended to be used in combination with Docker for Linux.
Author:   Robert Voelckner
Date:     Oct. 2020 - 2023
"""
import platform
import pwd
from typing import List, Union, Tuple
import subprocess
import shlex
import os
import signal
from datetime import datetime
from threading import Event
import time
import sys
import argparse
from configparser import ConfigParser
from pathlib import Path

import psutil

from regex import check_commandline_validity, split_user_and_commandline

# logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)
#
# FORMATTER = logging.Formatter("%(asctime)s - %(levelname)s - line %(lineno)s - %(message)s")
# LOG_HANDLER = logging.StreamHandler(sys.stdout)
# LOG_HANDLER.setLevel(logging.DEBUG)
# LOG_HANDLER.setFormatter(FORMATTER)
# LOG_HANDLER.setLevel(logging.DEBUG)
# logger.addHandler(LOG_HANDLER)

_CURRENT_USERNAME = pwd.getpwuid(os.getuid()).pw_name  # Name of the user this process was started by.

SECTION_RUN = "RUN"
SECTION_RUN_ONCE = "RUN_ONCE"
SECTION_TERMINATE_AND_RUN = "TERMINATE_AND_RUN"

# Signal stuff
_SHUTDOWN_EVENT = Event()  # Will be set if this process receives SIGTERM/SIGINT signal
_SIGTERM_TIMEOUT = 9.0
_SIGNALS__NAMES = {signal.SIGINT: "SIGINT", signal.SIGTERM: "SIGTERM"}
_DEFAULT_SIGINT_HANDLER = signal.getsignal(signal.SIGINT)
_DEFAULT_SIGTERM_HANDLER = signal.getsignal(signal.SIGTERM)


def split_commandline(commandline: str) -> Tuple[str, List[str]]:
    args = shlex.split(commandline)
    if len(args) == 1:
        return args[0], []
    else:
        return args[0], args[1:]


def has_suitable_commandline(commandline: str, process_executable: str, process_args: List[str]) -> bool:
    """
    Decides if a process has been created from a certain commandline.

    :param commandline: Commandline string that the process might have been created with.
    :param process_executable: Path + Name of the process executable
    :param process_args: Additional args of the process
    :return: Returns if the process was created using the given commandline.
    """
    def clean_args(args: List[str]) -> List[str]:
        args = [arg.strip() for arg in args]
        for i, arg in enumerate(args):
            while "//" in arg:
                arg = arg.replace("//", "/")
            args[i] = arg
        return args

    cmd_executable, cmd_args = split_commandline(commandline)
    cmd_args = clean_args(cmd_args)
    process_args = clean_args(process_args)
    if "/" in cmd_executable and "/" in process_executable:
        cmd_executable__path = os.path.dirname(os.path.abspath(cmd_executable))
        process_executable__path = os.path.dirname(os.path.abspath(process_executable))
        if cmd_executable__path != process_executable__path:
            return False
    cmd_executable__basename = os.path.basename(cmd_executable)
    process_executable__basename = os.path.basename(process_executable)
    if cmd_executable__basename.startswith(process_executable__basename) or process_executable__basename.startswith(cmd_executable__basename):
        if all(arg in process_args for arg in cmd_args):
            return True
    return False


def get_process_pids(commandlines: Union[str, List[str]], exclude_p_open_handles: List = None) -> List[int]:
    """
    Returns the PIDs of multiple processes.

    :param commandlines: Commandline strings of the processes whose PIDs we want to determine.
    :param exclude_p_open_handles: If not None, this may contain a list process handles (generated by subprocess.Popen). In this case, these processes' PIDs will be excluded from returned PIDs list.
    :return: Returns a list of PIDs.
    """
    if not isinstance(commandlines, List):
        commandlines = [commandlines]
    commandlines = [split_user_and_commandline(cmd)[1] for cmd in commandlines]  # Remove potential §user=xxxx§ prefixes
    pids = set()
    for commandline in commandlines:
        for process_ in psutil.process_iter(attrs=["pid", "cmdline", "name"]):
            try:
                proc_args = process_.cmdline()
                proc_exe = process_.name()
                proc_pid = process_.pid
                if proc_pid != 1 and process_.status() != "zombie" and \
                        has_suitable_commandline(commandline, process_executable=proc_exe, process_args=proc_args):
                    pids.add(proc_pid)
            except psutil.NoSuchProcess:
                pass  # Occurs if a process stopped before we could access its cmdline/name/pid
    if exclude_p_open_handles is not None:
        exclude_pids = set([handle.pid for handle in exclude_p_open_handles])
        pids = pids.difference(exclude_pids)
    return list(pids)


def term_processes(commandlines: Union[str, List[str]], sigterm_timeout: float = None,
                   p_open_handles: List[subprocess.Popen] = None) -> None:
    """
    Kills process(es). Prior to that - if desired - the processes are sent SIGTERM.

    :param commandlines: Commandline strings of processes to terminate. List may be empty.
    :param sigterm_timeout: If not None, the processes will be sent SIGTERM prior to kill. Contains the timeout (seconds) as float.
    :param p_open_handles: If not None, this may contain a list process handles. These processes will be killed as well.
    """
    if not isinstance(commandlines, List):
        commandlines = [commandlines]
    if not p_open_handles:
        p_open_handles = []

    _commandlines__pids = get_process_pids(commandlines, exclude_p_open_handles=p_open_handles)

    def _get_n_processes() -> int:
        """Returns the number of processes yet to be terminated."""
        # First, filter out those handles whose processes have already been terminated
        _still_running_handles = [handle for handle in p_open_handles if handle.poll() is None]
        p_open_handles.clear()
        p_open_handles.extend(_still_running_handles)
        return len(_commandlines__pids) + len(p_open_handles)

    if _get_n_processes() == 0:
        return
    print(f"Terminating {_get_n_processes()} processes")
    if sigterm_timeout is not None:
        print("  Sending SIGTERM.. ", end="")
        for pid in _commandlines__pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        for handle in p_open_handles:
            handle.send_signal(signal.SIGTERM)
        started_at = datetime.now()
        while _get_n_processes() and (datetime.now() - started_at).total_seconds() < sigterm_timeout:
            time.sleep(0.2)
            _commandlines__pids = get_process_pids(commandlines, exclude_p_open_handles=p_open_handles)
        if _get_n_processes() > 0:
            print(f"Timeout, {_get_n_processes()} processes still alive")
        else:
            print(f"All terminated after {(datetime.now()-started_at).total_seconds():.1f}s")
    if _get_n_processes() > 0:
        print("  Sending SIGKILL.. ", end="")
        for pid in _commandlines__pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        for handle in p_open_handles:
            handle.send_signal(signal.SIGKILL)
        print("Done")
    print()


def run_processes_in_background(run: List[str], run_once: List[str], terminate_and_run: List[str]) \
        -> List[subprocess.Popen]:
    """Runs commands as new processes. Returns Popen handles."""
    term_processes(terminate_and_run, sigterm_timeout=_SIGTERM_TIMEOUT)
    p_open_handles = []

    def p_open(full_cmd_: str) -> None:
        _cmd_user, _split_cmd = split_user_and_commandline(full_cmd_)  # Splits up e.g. "§user=xxxx§python bla.py"
        if _cmd_user is not None and _CURRENT_USERNAME not in ("root", _cmd_user):
            print(f"Cannot run as user '{_cmd_user}', since I am not the root user!")
            exit(-1)
        if "|" in _split_cmd:
            handle = subprocess.Popen(_split_cmd, start_new_session=True, shell=True, user=_cmd_user)
        else:
            handle = subprocess.Popen(shlex.split(_split_cmd), start_new_session=True, user=_cmd_user)
        p_open_handles.append(handle)

    print(f"Starting {sum(len(a) for a in (run, run_once, terminate_and_run))} process(es)..")
    for _cmd in run:
        print(f"  - {_cmd}")
        p_open(_cmd)

    for _cmd in run_once + terminate_and_run:
        print(f"  - {_cmd}  ", end="")
        if len(get_process_pids(_cmd)) > 0:
            print("->  Already runs")
            continue
        print()
        p_open(_cmd)

    print()
    return p_open_handles


def __handle_signal(sig, frame):
    _SHUTDOWN_EVENT.set()
    print(f"Received {_SIGNALS__NAMES[sig]}. 'Shutdown' flag is now set. Termination of processes follows shortly.")
    # Re-install original Python signal handlers
    signal.signal(signal.SIGTERM, _DEFAULT_SIGTERM_HANDLER)
    signal.signal(signal.SIGINT, _DEFAULT_SIGINT_HANDLER)


def parse_runfile(file_path: Path, run: List[str], run_once: List[str], terminate_and_run: List[str]):
    """Parses a given runfile and adds the obtained commandline strings to the provided lists."""
    _parser = ConfigParser(delimiters="\n", allow_no_value=True)
    _parser.read(file_path)
    _sections = [(SECTION_RUN, run), (SECTION_RUN_ONCE, run_once), (SECTION_TERMINATE_AND_RUN, terminate_and_run)]
    n = 0
    for pair in _sections:
        section_name = pair[0]
        dest_list = pair[1]
        if _parser.has_section(section_name):
            params = _parser.items(section_name)
            params = [tple[0] for tple in params]
            for param in params:
                param = param.strip()
                if param not in dest_list:
                    dest_list.append(param)
                    n += 1
    print(f"Successfully read {n} entries from runfile.")


if __name__ == '__main__':
    if platform.system().lower() != "linux":
        print("This script is intended only to be run on Linux. Exiting now.")
        exit(-1)

    _script_path = Path(__file__).resolve().parent
    _default_runfile_path = _script_path / f"{Path(__file__).stem}.ini"

    _parser = argparse.ArgumentParser(description="Runs multiple processes and forwards Unix SIGTERM/SIGINT signals to "
                                                  "them, if present. Processes may be long-running applications, as "
                                                  "well as complex shell commands.")
    _parser.add_argument("--run", "-r", type=str, action="append", metavar="COMMAND", dest="run",
                         help="Runs a process, regardless if it already runs.")
    _parser.add_argument("--run-once", "-r-once", type=str, action="append", metavar="COMMAND", dest="run_once",
                         help="Runs an application, but only if it doesn't run yet.")
    _parser.add_argument("--terminate-and-run", "-r-term", type=str, action="append", metavar="COMMAND", dest="terminate_and_run",
                         help=f"Before running the application, terminate all other instances of it. Makes use of "
                              f"SIGTERM and (after a timeout of {_SIGTERM_TIMEOUT}s) KILL.")
    _parser.add_argument("--block", action="store_true", dest="block",
                         help="Block after starting the applications. When receiving SIGTERM/SIGINT, forward SIGTERM to "
                              "applications.")
    _parser.add_argument("--file", "-f", default=str(_default_runfile_path), type=str,
                         help=f"Runfile (ini file) that provides startup processes. If 'None', only commandline args are"
                              f"used. Valid ini sections are [{SECTION_RUN}], [{SECTION_RUN_ONCE}] and "
                              f"[{SECTION_TERMINATE_AND_RUN}].")
    _args = _parser.parse_args()

    print("Application cmdline args:\n - " + "\n - ".join(f'{key} = {value}' for key, value in _args.__dict__.items()))
    print()

    _processes_run = list(_args.run) if _args.run else []
    _processes_run_once = list(_args.run_once) if _args.run_once else []
    _processes_terminate_and_run = list(_args.terminate_and_run) if _args.terminate_and_run else []

    # Parse .ini file, if possible
    if _args.file.strip() != "" and _args.file.strip().lower() != "none":
        _runfile_path = Path(_args.file)
        assert _runfile_path.is_file(), f"Given runfile '{_runfile_path}' either not exists or is no file!"
        parse_runfile(_runfile_path, _processes_run, _processes_run_once, _processes_terminate_and_run)

    _n_commands = sum(len(p) for p in (_processes_run, _processes_run_once, _processes_terminate_and_run))
    if _n_commands == 0:
        print("No run commands available. Exiting.")
        exit(0)

    # Check the run commands for formal validity
    print(f"Checking {_n_commands} run commands for formal validity.. ", end="")
    for _cmd in _processes_run + _processes_run_once + _processes_terminate_and_run:
        if check_commandline_validity(_cmd) is False:
            print(f"Failed\n --> Run command '{_cmd}' is invalid!")
            exit(-1)
    print("Passed")
    print()

    print(f"{SECTION_RUN} = {_processes_run}")
    print(f"{SECTION_RUN_ONCE} = {_processes_run_once}")
    print(f"{SECTION_TERMINATE_AND_RUN} = {_processes_terminate_and_run}")
    print()

    # Start our processes
    _p_open_handles: List[subprocess.Popen] = run_processes_in_background(
        run=_processes_run, run_once=_processes_run_once, terminate_and_run=_processes_terminate_and_run)

    if _args.block:
        print(f"Blocking now indefinitely until receiving {'/'.join([s for s in _SIGNALS__NAMES.values()])}")
        signal.signal(signal.SIGTERM, __handle_signal)
        signal.signal(signal.SIGINT, __handle_signal)
        sys.stdout.flush()  # Sometimes half of the previously printed messages got lost
        while not _SHUTDOWN_EVENT.is_set():
            _SHUTDOWN_EVENT.wait(timeout=1)
            # From time to time, read the return values of our started applications to avoid zombie processes
            _non_null: List[bool] = [handle.poll() is not None for handle in _p_open_handles]
            if any(_non_null):
                _p_open_handles = [handle for handle in _p_open_handles if handle.poll() is None]
                print(f"  - {sum(_non_null)} process(es) exited, {len(_p_open_handles)} still running..", flush=True)

        print()
        term_processes(commandlines=_processes_run + _processes_run_once + _processes_terminate_and_run,
                       sigterm_timeout=_SIGTERM_TIMEOUT, p_open_handles=_p_open_handles)

    sys.exit(0)
