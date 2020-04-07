#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import os.path
import shutil

from leaderf.devicons import *
from leaderf.explorer import *
from leaderf.manager import *
from leaderf.utils import *
from utils import (NO_CONTENT_MSG, accessable, cd, echo_cancel, invalid_line,
                   nearestAncestor)

MODE_DICT = {"NORMAL": "", "COPY": "[COPY] "}

help_dict = dict()


def help(text):
    def decorator(func):
        def inner_func(*args, **kwargs):
            return func(*args, **kwargs)

        help_dict[func.__name__.replace("command__", "")] = text
        return inner_func

    return decorator


# *****************************************************
# FilerExplorer
# *****************************************************
class FilerExplorer(Explorer):
    def __init__(self):
        # filename: {
        #   "isdir": bool,
        #   "fullpath": str
        # }
        self._contents = dict()
        self._cwd = None
        self._show_hidden_files = lfEval("get(g:, 'Lf_FilerShowHiddenFiles', 0)") == "1"
        self._show_devicons = lfEval("get(g:, 'Lf_ShowDevIcons', 1)") == "1"
        # NORMAL or COPY
        self._command_mode = "NORMAL"

    def getContent(self, *args, **kwargs):
        self._cwd = self._cwd or os.getcwd()
        return self.getFreshContent()

    def getFreshContent(self, *args, **kwargs):
        self._contents = dict()

        contents = {
            lfEncode(f): {
                "isdir": os.path.isdir(os.path.join(self._cwd, f)),
                "fullpath": os.path.join(self._cwd, f),
            }
            for f in os.listdir(self._cwd)
        }

        # hide dotfiles
        if not self._show_hidden_files:
            contents = {k: v for k, v in contents.items() if not k.startswith(".")}

        if self._show_devicons:
            self._prefix_length = webDevIconsStrLen()

        for k, v in contents.items():
            if self._show_devicons:
                icon = webDevIconsGetFileTypeSymbol(k, v["isdir"])
                k = icon + k
            if v["isdir"]:
                k += "/"
            self._contents[k] = v

        # Sort directories and files by each
        files = sorted([k for k, v in self._contents.items() if not v["isdir"]])
        dirs = sorted([k for k, v in self._contents.items() if v["isdir"]])

        if lfEval("get(g:, 'Lf_FilerShowCurrentDirDot', 0)") == "1":
            # . => current directory
            return ["."] + dirs + files
        else:
            if len(dirs + files) == 0:
                return [NO_CONTENT_MSG]
            return dirs + files

    def getStlCategory(self):
        return "Filer"

    def getStlCurDir(self):
        return MODE_DICT.get(self._command_mode, "") + escQuote(lfEncode(self._cwd))

    def getCwd(self):
        return self._cwd

    def supportsMulti(self):
        return True

    def setCommandMode(self, mode):
        """
        "NORMAL" or "COPY"
        """
        self._command_mode = mode

    def getPrefixLength(self):
        return self._prefix_length


# *****************************************************
# FilerExplManager
# *****************************************************
class FilerExplManager(Manager):
    def __init__(self):
        super(FilerExplManager, self).__init__()
        self._update_insert_maps()
        self._copy_file = ""
        self._copy_mode = False
        # self._copy_file_matchids = {}
        self._commands = self._get_commands()
        self._help_text_list = []

    def _get_commands(self):
        return [
            x[len("command__") :] for x in self.__dir__() if x.startswith("command__")
        ]

    def _update_insert_maps(self):
        insert_map = lfEval("leaderf#Filer#InsertMap()")
        maps = {key.upper(): cmd for key, cmd in insert_map.items()}
        self._getInstance()._cli._key_dict = maps

    def _getExplClass(self):
        return FilerExplorer

    def _defineMaps(self):
        lfCmd("call leaderf#Filer#Maps()")

    def accept(self, mode=""):
        instance = self._getInstance()
        line = instance.currentLine
        pattern = "".join(instance._cli._cmdline)

        if line in ("", NO_CONTENT_MSG):
            self._edit(pattern)
            return

        super(FilerExplManager, self).accept(mode)

    def _acceptSelection(self, *args, **kwargs):
        path = args[0]
        if path == NO_CONTENT_MSG:
            return

        if path == ".":
            path = self._getExplorer().getCwd()
        else:
            path = self._getDigest(path, 0)

        if not os.path.isabs(path):
            path = os.path.join(self._getExplorer().getCwd(), lfDecode(path))
            path = os.path.normpath(lfEncode(path))

        if os.path.isdir(path):
            cmd = lfEval("get(g:, 'Lf_FilerAcceptDirSelectionCmd', 'lcd')")
            lfCmd("%s %s" % (cmd, escSpecial(path)))
            return

        # from manager.py
        try:
            if kwargs.get("mode", "") != "t" or (
                lfEval("get(g:, 'Lf_DiscardEmptyBuffer', 0)") == "1"
                and len(vim.tabpages) == 1
                and len(vim.current.tabpage.windows) == 1
                and vim.current.buffer.name == ""
                and len(vim.current.buffer) == 1
                and vim.current.buffer[0] == ""
                and not vim.current.buffer.options["modified"]
            ):

                if vim.current.buffer.options["modified"]:
                    lfCmd("hide edit %s" % escSpecial(path))
                else:
                    lfCmd("edit %s" % escSpecial(path))
            else:
                lfCmd("tab drop %s" % escSpecial(path))
        except vim.error as e:  # E37
            lfPrintError(e)

    def _createHelp(self):
        if self._help_text_list:
            return self._help_text_list

        help = []
        key_cmd_dict = dict()
        for [key, cmd_name] in lfEval("leaderf#Filer#NormalMap()").items():
            key_cmd_dict[cmd_name] = key_cmd_dict.get(cmd_name, []) + [key]

        # sort key
        for [key, val] in key_cmd_dict.items():
            key_cmd_dict[key] = sorted(val)

        for [name, text] in help_dict.items():
            if name in key_cmd_dict:
                # key1/key2 : help text
                line = '" {} : {}'.format("/".join(key_cmd_dict[name]), text)
                help.append(line)
        help.sort()
        help.append('" ---------------------------------------------------------')

        self._help_text_list = help
        return help

    def do_command(self, cmd_name):
        return eval("self.command__{}()".format(cmd_name))

    def _cmdExtension(self, cmd_name):
        """
        this function can be overridden to add new cmd
        if return true, exit the input loop
        """

        if cmd_name in self._commands:
            return self.do_command(cmd_name)
        elif equal(cmd_name, "nop"):
            pass

    def _getDigest(self, line, mode):
        if not line:
            return ""

        prefix_len = self._getExplorer().getPrefixLength()
        return line[prefix_len:]

    def _getDigestStartPos(self, line, mode):
        return webDevIconsBytesLen()

    def _beforeEnter(self):
        super(FilerExplManager, self)._beforeEnter()
        self._copy_file = ""
        self._copy_mode = False
        self._getExplorer().setCommandMode("NORMAL")

    def _afterEnter(self):
        super(FilerExplManager, self)._afterEnter()

        winid = None

        if self._getInstance().getWinPos() == "popup":
            lfCmd(
                """call win_execute(%d, 'let matchid = matchadd(''Lf_hl_filerFile'', ''^[^\/]\+\(\/\)\@!$'')')"""
                % self._getInstance().getPopupWinId()
            )
            id = int(lfEval("matchid"))
            self._match_ids.append(id)

            lfCmd(
                """call win_execute(%d, 'let matchid = matchadd(''Lf_hl_filerDir'', ''^[^\/]\+\/$'')')"""
                % self._getInstance().getPopupWinId()
            )
            id = int(lfEval("matchid"))
            self._match_ids.append(id)

            lfCmd(
                """call win_execute(%d, 'let matchid = matchadd(''Lf_hl_filerNoContent'', ''^%s$'')')"""
                % (self._getInstance().getPopupWinId(), NO_CONTENT_MSG)
            )
            id = int(lfEval("matchid"))
            self._match_ids.append(id)
            winid = self._getInstance().getPopupWinId()
        else:
            id = int(lfEval("matchadd('Lf_hl_filerFile', '^[^\/]\+\(\/\)\@!$')"))
            self._match_ids.append(id)
            id = int(lfEval("matchadd('Lf_hl_filerDir', '^[^\/]\+\/$')"))
            self._match_ids.append(id)
            id = int(
                lfEval("matchadd('Lf_hl_filerNoContent', '^%s$')" % NO_CONTENT_MSG)
            )
            self._match_ids.append(id)

        if lfEval("get(g:, 'Lf_FilerMoveCursorCufBuf', 0)") == "1":
            self._move_cursor_if_fullpath_match(self._cur_buffer.name)

        # devicons
        if self._getExplorer()._show_devicons:
            self._match_ids.extend(matchaddDevIconsExtension(r'^__icon__\ze\s\+\S\+\.__name__$', winid))
            self._match_ids.extend(matchaddDevIconsExact(r'^__icon__\ze\s\+__name__$', winid))
            self._match_ids.extend(matchaddDevIconsDefault(r'^__icon__', winid))

    def startExplorer(self, win_pos, *args, **kwargs):
        _dir = ""
        if kwargs.get("arguments", {}).get("directory"):
            _dir = kwargs.get("arguments", {}).get("directory")[0]
            _dir = os.path.expanduser(lfDecode(_dir))
            _dir = os.path.expandvars(_dir)
            _dir = os.path.abspath(_dir)

            if not os.path.exists(_dir):
                lfCmd(
                    "echohl ErrorMsg | redraw | echon "
                    "'Unknown directory `%s`' | echohl NONE" % _dir
                )
                return

            elif not accessable(_dir):
                lfCmd(
                    "echohl ErrorMsg | redraw | echon "
                    "' Permission denied `%s`' | echohl NONE" % _dir
                )
                return

        _dir = _dir or os.getcwd()

        # Set vars because super().startExplorer() is calling self._getExplorer()
        self._getExplorer()._cwd = _dir

        # To call _buildPrompt() in super().startExplorer()
        if lfEval("get(g:, 'Lf_FilerShowPromptPath', 1)") == '1':
            self._getInstance()._cli._additional_prompt_string = self._adjust_path(_dir)

        super(FilerExplManager, self).startExplorer(win_pos, *args, **kwargs)

        # super().startExplorer() updates cwd to os.getcwd()
        self._getInstance().setCwd(_dir)

    @help("open file/dir under cursor")
    def command__open_current(self):
        line = self._getInstance().currentLine
        if line == NO_CONTENT_MSG:
            return
        if line == "":
            return

        file_info = self._getExplorer()._contents[line]
        if not file_info["isdir"]:
            self.accept()
            return True

        if not accessable(file_info["fullpath"]):
            lfCmd(
                "echohl ErrorMsg | redraw | echon "
                "' Permission denied `%s`' | echohl NONE" % file_info["fullpath"]
            )
            return

        if self._getInstance().isReverseOrder():
            lfCmd("normal! G")
        else:
            self._gotoFirstLine()

        self._chcwd(os.path.abspath(file_info["fullpath"]))

    @help("show files in parent directory")
    def command__open_parent_or_clear_line(self):
        if len(self._getInstance()._cli._cmdline) > 0:
            self._refresh()
            return
        self._open_parent()

    @help("show files in parent directory")
    def command__open_parent_or_backspace(self):
        if len(self._getInstance()._cli._cmdline) > 0:
            # like <BS> in cli#input()
            self._cli._backspace()
            self._cli._buildPattern()

            # like <Shorten> in manager#input()
            cur_len = len(self._content)
            cur_content = self._content[:cur_len]
            self._index = 0
            self._search(cur_content)
            if self._getInstance().isReverseOrder():
                lfCmd("normal! G")
            else:
                self._gotoFirstLine()
            return
        self._open_parent()

    @help("show files in parent directory")
    def command__open_parent(self):
        self._open_parent()

    @help("toggle show hidden files")
    def command__toggle_hidden_files(self):
        self._getExplorer()._show_hidden_files = (
            not self._getExplorer()._show_hidden_files
        )
        self.refresh(normal_mode=False)

    @help("show files of directory where g:Lf_RootMarkers exists")
    def command__goto_root_marker_dir(self):
        root_markers = lfEval("g:Lf_RootMarkers")
        rootMarkersDir = nearestAncestor(root_markers, self._getExplorer().getCwd())
        if rootMarkersDir:
            # exists root_markers
            self._chcwd(os.path.abspath(rootMarkersDir))

    @help("move the cursor upward")
    def command__down(self):
        lfCmd("normal! j")
        self._previewResult(False)

    @help("move the cursor downward")
    def command__up(self):
        lfCmd("normal! k")
        self._previewResult(False)

    # def _page_up(self):
    #     lfCmd('normal! <PageUp>')
    #     self._previewResult(False)

    # def _page_down(self):
    #     lfCmd('normal! <PageDown>')
    #     self._previewResult(False)

    # def _left_mouse(self):
    #     lfCmd('normal! <LeftMouse>')
    #     self._previewResult(False)

    @help("preview the result")
    def command__preview(self):
        self._previewResult(True)

    @help("toggle this help")
    def command__toggle_help(self):
        self.toggleHelp()

    @help("quit")
    def command__quit(self):
        self.quit()

    @help("switch to input mode")
    def command__switch_insert_mode(self):
        self.input()

    @help("open the file under cursor")
    def command__accept(self):
        self.accept()

    @help("open the file under cursor in horizontal split window")
    def command__accept_horizontal(self):
        self.accept("h")

    @help("open the file under cursor in vertical split window")
    def command__accept_vertical(self):
        self.accept("v")

    @help("open the file under cursor new tabpage")
    def command__accept_tab(self):
        self.accept("t")

    @help("scroll up in the popup preview window (nvim only)")
    def command__page_up_in_preview(self):
        if lfEval("has('nvim')"):
            self._toUpInPopup()

    @help("scroll down in the popup preview window (nvim only)")
    def command__page_down_in_preview(self):
        if lfEval("has('nvim')"):
            self._toDownInPopup()

    @help("close popup preview window (nvim only)")
    def command__close_preview_popup(self):
        if lfEval("has('nvim')"):
            self._closePreviewPopup()

    @help("select multiple result")
    def command__add_selections(self):
        self.addSelections()

    @help("select all result")
    def command__select_all(self):
        self.selectAll()

    @help("clear all selections")
    def command__clear_selections(self):
        self.clearSelections()

    @help("create a directory")
    def command__mkdir(self):
        # For dir completion
        save_cwd = lfEval("getcwd()")
        cd(self._getExplorer()._cwd)

        try:
            dir_name = lfEval("input('Create Directory: ', '', 'dir')")
        except KeyboardInterrupt:  # Cancel
            echo_cancel()
            return
        finally:
            # restore
            cd(save_cwd)

        if dir_name == "":
            echo_cancel()
            return

        path = os.path.join(self._getExplorer()._cwd, dir_name)
        if os.path.isdir(os.path.join(self._getExplorer()._cwd, dir_name)):
            lfPrintError(" Already exists. '{}'".format(path))
            return

        os.makedirs(path)

        if lfEval("get(g:, 'Lf_FilerMkdirAutoChdir', 0)") == "1":
            self._chcwd(path)
        else:
            self._refresh()

        self._move_cursor_if_fullpath_match(path)

    @help("rename files and directories")
    def command__rename(self):
        line = self._getInstance().currentLine
        if len(self._selections) > 0:
            lfPrintError(" Rename does not support multiple files.")
            return

        if invalid_line(line):
            return

        fullpath = self._getExplorer()._contents[line]["fullpath"]
        basename = os.path.basename(fullpath)

        try:
            renamed = lfEval("input('Rename: ', '{}')".format(basename))
        except KeyboardInterrupt:  # Cancel
            echo_cancel()
            return

        if renamed == "":
            echo_cancel()
            return

        if renamed == basename:
            return

        to_path = os.path.join(os.path.dirname(fullpath), renamed)

        if os.path.exists(to_path):
            lfPrintError(" Already exists. '{}'".format(to_path))
            return

        os.rename(fullpath, to_path)
        self._refresh()
        self._move_cursor_if_fullpath_match(to_path)

    @help("copy files and directories under cursor")
    def command__copy(self):
        if len(self._selections) > 0:
            lfPrintError(" Copy does not support multiple files.")
            return

        line = self._getInstance().currentLine
        if invalid_line(line):
            return

        self._copy_file = self._getExplorer()._contents[line]["fullpath"]
        self._copy_mode = True
        lfCmd("echon ' Copied.'")
        # Updat estatus line
        self._getExplorer().setCommandMode("COPY")
        self._redrawStlCwd()

    @help("paste the file or directory")
    def command__paste(self):
        if not self._copy_mode:
            return

        fullpath = self._copy_file
        basename = os.path.basename(fullpath)

        cwd = self._getExplorer()._cwd

        to_path = os.path.join(cwd, basename)

        if os.path.exists(to_path):
            name, ext = os.path.splitext(basename)
            to_path = os.path.join(cwd, "{}_copy{}".format(name, ext))

        # *_copy があったら、だめ
        if os.path.exists(to_path):
            lfPrintError(" Already exists. '{}'".format(to_path))
            return

        if os.path.isdir(fullpath):
            # shutil.copytree(src, dst)
            shutil.copytree(fullpath, to_path)
        else:
            shutil.copy2(fullpath, to_path)

        self._refresh()
        self._move_cursor_if_fullpath_match(to_path)
        lfCmd("echon ' Pasted.'")

    @help("create a file")
    def command__create_file(self):
        try:
            file_name = lfEval("input('Create file: ')")
        except KeyboardInterrupt:
            echo_cancel()
            return

        if file_name == "":
            echo_cancel()
            return

        path = os.path.join(self._getExplorer()._cwd, file_name)
        if os.path.exists(path):
            lfPrintError(" Already exists. '{}'".format(path))
            return

        # create file
        open(path, "w").close()

        self._refresh()
        self._move_cursor_if_fullpath_match(path)

    @help("change the current directory to cwd of LeaderF-filer")
    def command__change_directory(self):
        cd(self._getExplorer()._cwd)
        lfCmd("echon ' cd {}'".format(self._getExplorer()._cwd))

    def _open_parent(self):
        cwd = self._getExplorer()._cwd or os.getcwd()
        abspath = os.path.abspath(os.path.join(cwd, ".."))
        self._chcwd(abspath)

        if self._getExplorer()._show_devicons:
            dir_icon = webDevIconsGetFileTypeSymbol('', True)
            pattern = r"\v^{}{}/$".format(dir_icon, os.path.basename(cwd))
        else:
            pattern = r"\v^{}/$".format(os.path.basename(cwd))

        self._move_cursor(pattern)

    def _move_cursor(self, pattern):
        if self._getInstance().getWinPos() == "popup":
            lfCmd(
                """call win_execute(%d, 'call search(''%s'')')"""
                % (self._getInstance().getPopupWinId(), pattern)
            )
            self._getInstance().mimicCursor()
            # keep cursor pos
            lfCmd(
                "call win_execute(%d, 'normal! jk')"
                % self._getInstance().getPopupWinId()
            )
            # lfCmd("call win_execute(%d, 'normal! 0')" % self._getInstance().getPopupWinId())
        else:
            lfCmd("call search('%s')" % pattern)
            lfCmd("normal! 0")

    def _move_cursor_if_fullpath_match(self, path):
        """
        Move the cursor to the line where fullpath matches path.
        """
        for line, info in self._getExplorer()._contents.items():
            if info["fullpath"] == path:
                self._move_cursor(line)
                break

    def _refresh(self, cwd=None):
        if cwd:
            if self._copy_mode:
                # update status line
                self._redrawStlCwd()
            else:
                self._redrawStlCwd(cwd)

            self._getInstance().setCwd(cwd)

        # initialize like startExplorer()
        self._index = 0
        self._result_content = []
        self._cb_content = []

        # add history
        self._cli.writeHistory(self._getExplorer().getStlCategory())

        # clear input pattern
        self._getInstance()._cli.clear()
        self.refresh(normal_mode=False)
        if lfEval("get(g:, 'Lf_FilerShowPromptPath', 1)") == '1':
            self._getInstance()._cli._additional_prompt_string = self._adjust_path(self._getExplorer()._cwd)
        self._getInstance()._cli._buildPrompt()

    def _edit(self, name):
        path = os.path.join(self._getExplorer().getCwd(), name)
        self._getInstance().exitBuffer()
        lfCmd("edit %s" % path)

    def _chcwd(self, path):
        self._getExplorer()._cwd = path
        self._refresh(cwd=path)
        if "--auto-cd" in self.getArguments():
            cd(path)

    def _previewInPopup(self, *args, **kwargs):
        line = args[0]
        if line == ".":
            return
        fullpath = self._getExplorer()._contents[line]["fullpath"]
        buf_number = lfEval("bufadd('{}')".format(escQuote(fullpath)))
        self._createPopupPreview(line, buf_number, 0)

    def _redrawStlCwd(self, cwd=None):
        if cwd is None:
            self._getInstance().setStlCwd(self._getExplorer().getStlCurDir())
        else:
            self._getInstance().setStlCwd(cwd)

        if self._getInstance().getWinPos() in ("popup", "floatwin"):
            self._getInstance().setPopupStl(self._current_mode)
            self._getInstance().refreshPopupStatusline()

    def _adjust_path(self, path):
        if os.name == 'nt':
            if len(path) == 3:
                return path
        else:
            if path == '/':
                return path
        path = lfEval("pathshorten('{}')".format(path))
        endchars = '\\' if os.name == "nt" else '/'
        return path + endchars

# *****************************************************
# filerExplManager is a singleton
# *****************************************************
filerExplManager = FilerExplManager()

__all__ = ["filerExplManager"]
