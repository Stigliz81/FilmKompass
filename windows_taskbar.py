"""Explicit taskbar identity for the native Tk wrapper; optional read-only diagnosis."""

def configure_shell(window, executable, icon, app_id):
    """Set one window's documented relaunch properties, without global registration."""
    import ctypes as c
    from ctypes import wintypes as w
    from pathlib import Path
    import subprocess,uuid
    executable,icon=Path(executable).resolve(),Path(icon).resolve()
    if not executable.is_file() or not icon.is_file():
        raise OSError('Taskleistenressource fehlt')
    u=c.windll.user32
    u.GetAncestor.argtypes=[w.HWND,w.UINT];u.GetAncestor.restype=w.HWND
    hwnd=u.GetAncestor(window.winfo_id(),2)
    if not hwnd:raise OSError('Tk-Wrapper fehlt')
    if getattr(window,'_shell_identity_hwnd',None)==hwnd:return int(hwnd)
    class Key(c.Structure):_fields_=[('guid',c.c_byte*16),('pid',w.DWORD)]
    def guid(value):return (c.c_byte*16).from_buffer_copy(uuid.UUID(value).bytes_le)
    store=c.c_void_p();iid=guid('886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99')
    shell=c.windll.shell32
    shell.SHGetPropertyStoreForWindow.argtypes=[w.HWND,c.c_void_p,c.POINTER(c.c_void_p)]
    if shell.SHGetPropertyStoreForWindow(hwnd,c.byref(iid),c.byref(store))!=0:
        raise OSError('Windows-Shell-Eigenschaften nicht verfügbar')
    table=c.cast(store,c.POINTER(c.POINTER(c.c_void_p))).contents
    set_value=c.WINFUNCTYPE(c.c_long,c.c_void_p,c.POINTER(Key),c.c_void_p)(table[6])
    commit=c.WINFUNCTYPE(c.c_long,c.c_void_p)(table[7])
    release=c.WINFUNCTYPE(w.ULONG,c.c_void_p)(table[2])
    buffers=[]
    try:
        # Relaunch command/display name are a pair. Set the explicit ID last.
        for pid,value in [(2,subprocess.list2cmdline([str(executable)])),
                          (3,str(icon)+',0'),(4,'FilmKompass'),(5,app_id)]:
            key=Key(guid('9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3'),pid)
            text=c.create_unicode_buffer(value);buffers.append(text)
            variant=c.create_string_buffer(24)
            c.c_ushort.from_buffer(variant).value=31  # borrowed VT_LPWSTR; SetValue copies it
            c.c_void_p.from_buffer(variant,8).value=c.addressof(text)
            if set_value(store,c.byref(key),variant)!=0:
                raise OSError('Taskleisten-Eigenschaft konnte nicht gesetzt werden')
        if commit(store)!=0:raise OSError('Taskleisten-Eigenschaften nicht übernommen')
        window._shell_identity_hwnd=hwnd
    finally:release(store)
    return int(hwnd)

def diagnose(window):
    import ctypes as c
    from ctypes import wintypes as w
    import uuid
    u=c.windll.user32
    u.GetParent.argtypes=[w.HWND];u.GetParent.restype=w.HWND
    u.GetAncestor.argtypes=[w.HWND,w.UINT];u.GetAncestor.restype=w.HWND
    u.GetWindow.argtypes=[w.HWND,w.UINT];u.GetWindow.restype=w.HWND
    u.SendMessageTimeoutW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM,w.UINT,w.UINT,c.POINTER(c.c_size_t)]
    u.GetWindowLongPtrW.argtypes=[w.HWND,c.c_int];u.GetWindowLongPtrW.restype=c.c_ssize_t
    u.GetClassLongPtrW.argtypes=[w.HWND,c.c_int];u.GetClassLongPtrW.restype=c.c_size_t
    u.GetClassNameW.argtypes=[w.HWND,w.LPWSTR,c.c_int]
    class Key(c.Structure):_fields_=[('guid',c.c_byte*16),('pid',w.DWORD)]
    def guid(s):return (c.c_byte*16).from_buffer_copy(uuid.UUID(s).bytes_le)
    def properties(hwnd):
        result={};store=c.c_void_p();iid=guid('886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99')
        shell=c.windll.shell32;shell.SHGetPropertyStoreForWindow.argtypes=[w.HWND,c.c_void_p,c.POINTER(c.c_void_p)]
        if shell.SHGetPropertyStoreForWindow(hwnd,c.byref(iid),c.byref(store))!=0:return {'unavailable':True}
        table=c.cast(store,c.POINTER(c.POINTER(c.c_void_p))).contents
        get=c.WINFUNCTYPE(c.c_long,c.c_void_p,c.POINTER(Key),c.c_void_p)(table[5])
        release=c.WINFUNCTYPE(w.ULONG,c.c_void_p)(table[2])
        try:
            for pid,name in [(2,'RelaunchCommand'),(3,'RelaunchIconResource'),(4,'RelaunchDisplayNameResource'),(5,'AppUserModelID')]:
                key=Key(guid('9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3'),pid);pv=c.create_string_buffer(24)
                if get(store,c.byref(key),pv)==0:
                    vt=c.cast(pv,c.POINTER(c.c_ushort))[0]
                    result[name]=c.cast(c.addressof(pv)+8,c.POINTER(c.c_wchar_p))[0] if vt==31 else None
                    c.windll.ole32.PropVariantClear(c.byref(pv))
        finally:release(store)
        return result
    client=window.winfo_id();root=u.GetAncestor(client,2)
    import os,sys,hashlib
    from pathlib import Path
    result={'launch':dict(executable_sha256=hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),cwd=str(Path.cwd()),diagnose_requested='--diagnose-taskbar' in sys.argv,profile_override=bool(os.environ.get('MOVIEPILOT_MANAGER_DATA_DIR'))), 'initialization':getattr(window,'_shell_initialization',{}),'tk_patchlevel':str(window.tk.call('info','patchlevel')),'tk_scaling':float(window.tk.call('tk','scaling')),'windows':[]}
    for hwnd in dict.fromkeys([client,u.GetParent(client),root]):
        if not hwnd:continue
        name=c.create_unicode_buffer(256);u.GetClassNameW(hwnd,name,256);icons={}
        for index in (0,1,2):
            value=c.c_size_t();u.SendMessageTimeoutW(hwnd,0x7f,index,0,2,500,c.byref(value));icons[str(index)]=bool(value.value)
        import os,sys
        pid=w.DWORD();u.GetWindowThreadProcessId.argtypes=[w.HWND,c.POINTER(w.DWORD)]
        u.GetWindowThreadProcessId(hwnd,c.byref(pid))
        result['windows'].append(dict(handle=int(hwnd),class_name=name.value,is_root=hwnd==root,
            process_id=int(pid.value),is_own_process=pid.value==os.getpid(),process_executable=sys.executable,
            owner=int(u.GetWindow(hwnd,4) or 0),extended_style=hex(u.GetWindowLongPtrW(hwnd,-20)),
            wm_geticon=icons,class_large_icon=bool(u.GetClassLongPtrW(hwnd,-14)),
            class_small_icon=bool(u.GetClassLongPtrW(hwnd,-34)),shell=properties(hwnd)))
    value=c.c_void_p();shell=c.windll.shell32
    shell.GetCurrentProcessExplicitAppUserModelID.argtypes=[c.POINTER(c.c_void_p)]
    if shell.GetCurrentProcessExplicitAppUserModelID(c.byref(value))==0:
        result['process_app_id']=c.wstring_at(value)
        c.windll.ole32.CoTaskMemFree.argtypes=[c.c_void_p];c.windll.ole32.CoTaskMemFree(value)
    return result
