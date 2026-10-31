"""Windows shell file drops for Tk, without an additional runtime dependency.

The native callback only queues paths; Tk processes them in its ordinary event loop.
API: https://learn.microsoft.com/windows/win32/shell/wm-dropfiles
"""
import ctypes as C
from ctypes import wintypes as W
import os


class DropTarget:
    def __init__(self, hwnd, receive):
        if os.name != 'nt':
            raise OSError('shell file drops require Windows')
        self.hwnd = hwnd
        self.receive = receive
        self.shell = C.WinDLL('shell32', use_last_error=True)
        self.common = C.WinDLL('comctl32', use_last_error=True)
        self.callback_type = C.WINFUNCTYPE(C.c_ssize_t, W.HWND, W.UINT, W.WPARAM, W.LPARAM,
                                          C.c_size_t, C.c_size_t)
        self.shell.DragAcceptFiles.argtypes = [W.HWND, W.BOOL]
        self.shell.DragAcceptFiles.restype = None
        self.shell.DragQueryFileW.argtypes = [W.HANDLE, W.UINT, W.LPWSTR, W.UINT]
        self.shell.DragQueryFileW.restype = W.UINT
        self.shell.DragFinish.argtypes = [W.HANDLE]
        self.shell.DragFinish.restype = None
        self.common.SetWindowSubclass.argtypes = [W.HWND, self.callback_type, C.c_size_t, C.c_size_t]
        self.common.SetWindowSubclass.restype = W.BOOL
        self.common.RemoveWindowSubclass.argtypes = [W.HWND, self.callback_type, C.c_size_t]
        self.common.RemoveWindowSubclass.restype = W.BOOL
        self.common.DefSubclassProc.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
        self.common.DefSubclassProc.restype = C.c_ssize_t
        self.callback = self.callback_type(self._message)  # strong reference until the window is destroyed
        self.token = id(self)
        if not self.common.SetWindowSubclass(hwnd, self.callback, self.token, 0):
            self.hwnd = None
            raise OSError('could not register shell file drops')
        self.shell.DragAcceptFiles(hwnd, True)

    def _message(self, hwnd, message, wparam, lparam, subclass, ref):
        if message == 0x233:  # WM_DROPFILES
            try:
                count = self.shell.DragQueryFileW(wparam, 0xFFFFFFFF, None, 0)
                # The UI accepts one package at a time. Keep two paths to report a multiple-file drop.
                files = []
                for i in range(min(count, 2)):
                    length = self.shell.DragQueryFileW(wparam, i, None, 0)
                    if not 0 < length <= 32767:
                        continue
                    buf = C.create_unicode_buffer(length + 1)
                    self.shell.DragQueryFileW(wparam, i, buf, length + 1)
                    files.append(buf.value)
                self.receive(files)
            except Exception:
                # No Python exception may cross a native window procedure boundary.
                pass
            finally:
                self.shell.DragFinish(wparam)
            return 0
        if message == 0x82:  # WM_NCDESTROY: remove the subclass before forwarding destruction
            self.common.RemoveWindowSubclass(hwnd, self.callback, self.token)
            self.hwnd = None
        return self.common.DefSubclassProc(hwnd, message, wparam, lparam)

    def close(self):
        if self.hwnd is not None:
            self.shell.DragAcceptFiles(self.hwnd, False)
            if not self.common.RemoveWindowSubclass(self.hwnd, self.callback, self.token):
                raise OSError('could not unregister shell file drops')
            self.hwnd = None
