# %%
from .util import * # the imported components will be available for other modules if "from .basedaq import *"

# %% [markdown]
'''
Python has no static variable, but class (not instance) variables serve as static variable
https://stackoverflow.com/questions/2398661/schedule-a-repeating-event-in-python-3#:~:text=You%20could%20use%20threading.Timer,%20but%20that
'''
# Base device class ------------------------------------------------------------------------
class daqBase:
    def __init__(self,daqid):
        self.daqid = daqid # board number
        self.daqinfo = None
        self.ai = None
        self.ao = None

    def config_ai(self, lowCh=0, highCh=1, **kwarg):
        raise NotImplementedError

    def config_ao(self, lowCh=0, highCh=1, **kwarg):
        raise NotImplementedError

# Base AO class definition ------------------------------------------------------------------------
class aoBase:
    set_endMode = {'hold','zero'}
    def __init__(self, daq, lowCh, highCh, **kwarg):
        self.daq = daq
        self.info = None
        self.sampleRate = 10000 # Hz/channel
        self.channel = [lowCh, highCh]
        self.isrunning = False
        self.data = []
        self.endMode = 'zero'
        self.startFcn = None # (function,(arg),{kwarg}); foo(eventdata,*arg,**kwarg)
        self.stopFcn = None # (function,(arg),{kwarg}); foo(eventdata,*arg,**kwarg)
        assignkwarg(self,**kwarg)
        
    def __del__(self):
        try:
            self.stop()
        except:
            pass

    def _assertVariable(self):
        # make sure the variables are valid
        assert self.sampleRate > 0, f'\'ao.sampleRate\' must be > 0. It is {self.sampleRate} now.'
        assert self.endMode in aoBase.set_endMode, f'\'ao.endMode\' must be one of {aoBase.set_endMode}'

    def start(self):
        '''
        Start AO output
        Syntax: ao.start()
        '''
        raise NotImplementedError

    def stop(self):
        '''
        Stop AO output
        Syntax: ao.stop()
        '''
        raise NotImplementedError
        
    def putvalue(self, voltage):
        '''
        This function output one sample for each AO channel.
        Syntax: putvalue([value 0, value 1,...])
        '''
        raise NotImplementedError
        
    def putdata(self, voltage):
        '''
        This function prepares voltage data for AO output.
        Syntax: putdata(numpy.ndarray)
        The data is a M x N matrix where M is the number of output channels.
        i.e. Data for each channel is in a row vector (opposite to MATLAB DAQ toolbox)
        '''
        raise NotImplementedError

# Base AI class definition ------------------------------------------------------------------------
class aiBase:
    set_grounding = {'single-ended','grounded','differential'} #cannot be defined in the inner class...
    set_trigType = {'instant','digital-positive-edge'}
    set_aqMode = {'foreground','background'}
    def __init__(self, daq, lowCh, highCh, **kwarg):
        self.daq = daq
        self.info = None
        self.sampleRate = 10000 # Hz/channel
        self.channel = [lowCh, highCh]
        self.grounding = 'single-ended' #e.g. single_ended
        self.trigType = 'instant'
        self.trigRepeat = 1 # put 0 for continous acquisition or Inf triggers
        self.trigFcn = None # (function,(arg),{kwarg}); foo(eventdata,*arg,**kwarg)
        self.iscontinuous = False # if not continuous -> acquires "samplesPerTrig" numbers of samples regardless of triggered daq or not
        self.samplesPerTrig = 1000 # in samples/channel
        self.samplesAcquired = 0 # number of samples/channel transferred to ai.data
        self.samplesAcquiredFcnCount = 0 # in samples/channel; 0 means no function to be called
        self.samplesAcquiredFcn = None # (function,(arg),{kwarg}); foo(eventdata,*arg,**kwarg)
        self.startFcn = None # (function,(arg),{kwarg}); foo(eventdata,*arg,**kwarg)
        self.stopFcn = None # (function,(arg),{kwarg}); foo(eventdata,*arg,**kwarg)
        self.isrunning = False
        self.aqMode = 'foreground' # acquisition mode
        self.data = [] # size of channel x sample
        #self.aitime = []
        self._nextdataidx = 0 # for aitime generation. It's the index (i.e. number of total transferred samples) to the 1st data point of the NEXT getdata() event. It will be updated in getdata()
        self._trigTime = [] # for aitime generation
        assignkwarg(self,**kwarg)
        
    def __del__(self):
        try:
            self.stop()
        except:
            pass

    def _assertVariable(self):
        # make sure the variables are valid
        assert self.grounding in aiBase.set_grounding, f'\'ai.grounding\' must be one of {aiBase.set_grounding}. It is {self.grounding} now.'
        assert self.aqMode in aiBase.set_aqMode, f'\'ai.aqMode\' must be one of {aiBase.set_aqMode}. It is {self.aqMode} now.'
        assert self.sampleRate > 0, f'\'ai.sampleRate\' must be > 0. It is {self.sampleRate} now.'
        assert self.trigType in aiBase.set_trigType, f'\'ai.trigType\' must be one of {aiBase.set_trigType}. It is {self.trigType} now.'
        assert ((type(self.trigRepeat) == int and self.trigRepeat >= 1)
                or (self.trigRepeat in ['inf','Inf'])), f'\'ai.trigRepeat\' must be an integer that is >= 1 or \'inf\'. It is {type(self.trigRepeat)} {self.trigRepeat} now.'
        assert ((type(self.samplesPerTrig) == int and self.samplesPerTrig >= 1)
                 or (self.samplesPerTrig in ['inf','Inf'])), f'\'ai.samplesPerTrig\' must be an integer that is >= 1 or \'inf\'. It is {type(self.samplesPerTrig)} {self.samplesPerTrig} now.'
        assert self.samplesAcquiredFcnCount >= 0 and type(self.samplesAcquiredFcnCount) == int, f'\'ai.samplesAcquiredFcnCount\' must be an integer that is >= 0. It is {type(self.samplesAcquiredFcnCount)} {self.samplesAcquiredFcnCount} now.'

    def start(self):
        '''
        Start acquisition
        Syntax: ai.start()
        '''
        raise NotImplementedError

    def stop(self):
        '''
        Stop acquisition
        Syntax: ai.stop()
        '''
        raise NotImplementedError
        
    def getvalue(self):
        '''
        This function get a single reading from each AI channel.
        Syntax: data = ai.getvalue()
        '''
        raise NotImplementedError
        
    def getdata(self,*arg,to_numpy=True):
        '''
        Get all or specified amount of data from the acquisition engine, starting from the earliest data point.
        Syntax: aitime, aidata = ai.getdata(1000) -> get 1000 acquired samples from each channel
                aitime, aidata = ai.getdata() -> get every available samples in the acquisition engine
            if to_numpy is True -> return np.ndarray else -> return python list
        '''
        raise NotImplementedError
    



