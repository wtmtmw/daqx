# %%
import threading, inspect, time


# %%
def createDevice(dev,daqid):
    set_daqdevice = {'mcc','ni'}
    assert dev in set_daqdevice, f'Device must be a member of {set_daqdevice}'
    if dev == 'mcc':
        from daqx.mccdaq import mccdaq
        return mccdaq(daqid)
    elif dev == 'ni':
        raise NotImplementedError

def assignkwarg(obj,**kwarg):
    for key, value in kwarg.items():
        if key in obj.__dict__:
            setattr(obj, key, value)
        else:
            print(f'\033[31mAttribute \'{key}\' does not exist -> skip\033[0m')

def getMethods(cls):
    methods = inspect.getmembers(cls, predicate=inspect.isfunction)
    #e.g. methods = [('__init__', <function mccdaq.__init__ at 0x00000195C9995AB0>), ('config_ai', <function mccdaq.config_ai at 0x00000195C9996320>), ('config_ao', <function mccdaq.config_ao at 0x00000195C72D7490>)]
    return [member[0] for member in methods if not member[0].startswith('_')] # list of strings
            
class rptTimer:
    '''
    timerobj = rptTimer(interval, function, autodt=True, *arg, **kwarg)
    timerobj.start()
    timerobj.stop()
    '''
    def __init__(self, interval, function, *arg, autodt=True, verbose = True, **kwarg):
        self.interval = interval
        self.function = function
        self.autodt = autodt
        self.arg = arg
        self.kwarg = kwarg
        self.verbose = verbose
        self._stopping = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._dt = interval       # Current interval
        
    def __del__(self):
        try:
            self.stop()
        except:
            pass

    def _run(self):
        while not self._stopping.is_set():
            # Call the function asynchronously
            starttime = time.time()
            self.function(*self.arg, **self.kwarg)
            exetime = time.time() - starttime
            
            # Adjust interval if busy and autodt is enabled
            if exetime > self._dt:
                if self.autodt:
                    self._dt = exetime + 0.01
                    if self.verbose:
                        print(f'Timer interval adjusted to {self._dt}s')
                else:
                    if self.verbose:
                        print(f'Execution time ({exetime}s) is longer than timer interval')

            # Wait for remaining time
            wait_time = self._dt - exetime
            if wait_time > 0:
                self._stopping.wait(wait_time)

    def start(self):
        if not self._thread.is_alive():
            self._stopping.clear()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def stop(self):
        self._stopping.set()
        self._thread.join() #ensure the background thread is properly stopped and cleaned up before the program continues or exits