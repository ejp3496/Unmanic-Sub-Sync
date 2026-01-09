#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    example_worker_process

    UNMANIC PLUGINS OVERVIEW:

        Plugins are stand-alone Python modules that are executed at defined stages during
        the optimisation process.

        The Plugin class is made up of defined "runner" functions. For each of these functions,
        whatever parameters are provided must also be returned in the form of a tuple.

        A Plugin class may contain any number of plugin "runner" functions, however they may
        only have one of each type.

        A Plugin class may be configured by providing a dictionary "Settings" class in it's header.
        This will be accessible to users from within the Unmanic Plugin Manager WebUI.
        Plugin settings will be callable from any of the Plugin class' "runner" functions.

        A Plugin has limited access to the Unmanic process' data. However, there is no limit
        on what a plugin may carryout when it's "runner" processes are called. The only requirement
        is that the data provided to the "runner" function is returned once the execution of that
        function is complete.

        A System class has been provided to feed data to the Plugin class at the discretion of the
        Plugin's developer.
        System information can be obtained using the following syntax:
            ```
            system = System()
            system_info = system.info()
            ```
        In this above example, the system_info variable will be filled with a dictionary of a range
        of system information.

    THIS EXAMPLE:

        > The Worker Process Plugin runner
            :param data     - Dictionary object of data that will configure how the FFMPEG process is executed.

"""
import os
import logging
import shlex
from collections import Counter

from unmanic.libs.unplugins.settings import PluginSettings
from unmanic.libs.directoryinfo import UnmanicDirectoryInfo
from unmanic.libs.system import System
from sub_sync.lib.ffmpeg import Parser, Probe
# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.sub_sync")

class Settings(PluginSettings):
    """
    An object to hold a dictionary of settings accessible to the Plugin
    class and able to be configured by users from within the Unmanic WebUI.

    This class has a number of methods available to it for accessing these settings:

        > get_setting(<key>)            - Fetch a single setting value. Or leave the
                                        key argument empty and return the full dictionary.
        > set_setting(<key>, <value>)   - Set a singe setting value.
                                        Used by the Unmanic WebUI to save user settings.
                                        Settings are stored on disk in order to be persistent.

    """
    settings = {}

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)

        self.form_settings = {}

def subs_already_synced(path):
    directory_info = UnmanicDirectoryInfo(os.path.dirname(path))

    # compare list of synced SRT files to those found in the same dir
    try:
        already_synced = directory_info.get('subs_synced', os.path.basename(path).lower())
    except Exception as e:
        logger.debug("Unknown exception {}.".format(e))
        already_synced = ''

    files = os.listdir(os.path.dirname(path))
    srts = []
    for file in files:
        if os.path.splitext(file)[1].lower() == ".srt" and os.path.splitext(os.path.basename(path))[0] in file:
            srts.append(file)

    logger.debug("already_synced: {}".format(already_synced))
    logger.debug("srts: {}".format(srts))
    if Counter(already_synced) == Counter(srts):
        logger.debug("File's subtitles were previously synced with {}.".format(already_synced))
        return True

    # Default to...
    return False

def on_library_management_file_test(data):
    """
    Runner function - enables additional actions during the library management file tests.

    The 'data' object argument includes:
        library_id                      - The library that the current task is associated with
        path                            - String containing the full path to the file being tested.
        issues                          - List of currently found issues for not processing the file.
        add_file_to_pending_tasks       - Boolean, is the file currently marked to be added to the queue for processing.
        priority_score                  - Integer, an additional score that can be added to set the position of the new task in the task queue.
        shared_info                     - Dictionary, information provided by previous plugin runners. This can be appended to for subsequent runners.

    :param data:
    :return:

    """

    # Get the path to the file
    abspath = data.get('path')
    #just look for mp4s becuase ffsubsync only works with mp4s
    logger.debug("Looking at file extension {} from file {}".format(os.path.splitext(abspath)[1].lower(),abspath))
    if os.path.splitext(abspath)[1].lower() == ".mp4":
        if not subs_already_synced(abspath):
            # Mark this file to be added to the pending tasks
            data['add_file_to_pending_tasks'] = True
            logger.debug("File '{}' should be added to task list. File has not been previously been synced.".format(abspath))
        else:
            logger.debug("File '{}' has been previously been synced.".format(abspath))

    return data

def on_worker_process(data):
    """
    Runner function - enables additional configured processing jobs during the worker stages of a task.

    The 'data' object argument includes:
        exec_command            - A command that Unmanic should execute. Can be empty.
        command_progress_parser - A function that Unmanic can use to parse the STDOUT of the command to collect progress stats. Can be empty.
        file_in                 - The source file to be processed by the command.
        file_out                - The destination that the command should output (may be the same as the file_in if necessary).
        original_file_path      - The absolute path to the original file.
        repeat                  - Boolean, should this runner be executed again once completed with the same variables.

    :param data:
    :return:
    """
    settings = Settings()
    system = System()
    system_info = system.info()

    # Default to no FFMPEG command required. This prevents the FFMPEG command from running if it is not required
    data['exec_command'] = []
    data['repeat'] = False

    custom_string = settings.get_setting('insert_string_into_srt_file_name')
    runcommand = settings.get_setting('execute_command')
    # Get the path to the file
    abspath = data.get('original_file_path')

    #get file probe
    probe = Probe(logger, allowed_mimetypes=['video'])
    if not probe.file(abspath):
        # File probe failed, skip the rest of this test
        logger.warning("Failed probed for file {}").format(abspath)
        return

    #look for SRT files with the same name and add them to the command with bash -c
    allfiles = os.listdir(os.path.dirname(abspath))
    srtfiles = []
    for file in allfiles:
        if os.path.splitext(file)[1] == ".srt" and os.path.splitext(os.path.basename(abspath))[0] in file:
            srtfiles.append(file)

    logger.debug("list of found SRT files: {}".format(srtfiles))
    # don't do anything if srt files aren't found
    if len(srtfiles) < 1:
        return data

    longcommand = ""
    for srt in srtfiles:
        logger.debug("Adding command for {} and {}".format(abspath, srt))
        longcommand += "ffsubsync {} -i {} -o {} --gss;".format(shlex.quote(abspath), shlex.quote(os.path.join(os.path.dirname(abspath),srt)), shlex.quote(os.path.join(os.path.dirname(abspath),srt)))
    longcommand = longcommand[:-2]

    data['exec_command'] = ['bash', '-c', longcommand]  # using bash -c to run multiple commands with ;

    # Set the parser
    if data['exec_command']:
        parser = Parser(logger)
        parser.set_probe(probe)
        data['command_progress_parser'] = parser.parse_progress

    return data

def on_postprocessor_task_results(data):
    """
    Runner function - provides a means for additional postprocessor functions based on the task success.

    The 'data' object argument includes:
        task_processing_success         - Boolean, did all task processes complete successfully.
        file_move_processes_success     - Boolean, did all postprocessor movement tasks complete successfully.
        destination_files               - List containing all file paths created by postprocessor file movements.
        source_data                     - Dictionary containing data pertaining to the original source file.

    :param data:
    :return:

    """
    # We only care that the task completed successfully.
    # If a worker processing task was unsuccessful, dont mark the file streams as kept
    # write all SRT files synced in a list
    # the problem here is there is a race condition where if an SRT file gets add while syncing other SRTs for the same
    # mp4 it will get marked as synced even though it isn't
    if not data.get('task_processing_success'):
        return data

    for destination_file in data.get('destination_files'):
        directory_info = UnmanicDirectoryInfo(os.path.dirname(destination_file))
        logger.debug("received data object {}".format(data))
        logger.debug("received source_data object {}".format(data))
        allfiles = os.listdir(os.path.dirname(destination_file))
        srtfiles = []
        for file in allfiles:
            if os.path.splitext(file)[1] == ".srt" and os.path.splitext(os.path.basename(destination_file))[0] in file:
                srtfiles.append(file)
        directory_info.set('subs_synced', os.path.basename(destination_file),srtfiles)
        directory_info.save()
        logger.info("subtitles synced for '{}' and recorded in .unmanic file.".format(destination_file))
    return data
