# %%
from .basedaq import * # all .util components were imported in .basedaq already
import ctypes
from mcculw import ul
from mcculw.enums import ScanOptions, FunctionType, BoardInfo, InfoType, ULRange, TrigType, AnalogInputMode, Status
from mcculw.device_info import DaqDeviceInfo
from math import ceil
import traceback # error handling
import numpy as np
import time

# %%
# mcc device class definition ------------------------------------------------------------------------
class mccdaq(daqBase):
    def __init__(self,daqid):
        super().__init__(daqid)
        self.daqinfo = DaqDeviceInfo(self.daqid)
        self.eventlistener = self._listener(self)

        
    def config_ai(self, lowCh=0, highCh=1, **kwarg):
        self.ai = mcc_ai(self, lowCh, highCh,
                         info = self.daqinfo.get_ai_info(), **kwarg)

    def config_ao(self, lowCh=0, highCh=1, **kwarg):
        self.ao = mcc_ao(self, lowCh, highCh, 
                         info = self.daqinfo.get_ao_info(), **kwarg)

    class _listener:
        def __init__(self,daq,**kwarg):
            self.islistening = False
            self.daq = daq
            # self.checkai = None # if any event callback is assigned -> check in the listener
            # self.checkao = None # function handle or None
            self.aistatus = None # AI status when checked last time
            self.aostatus = None # AO status when checked last time
            self.samplesAcquiredQuotient = 0 # samplesAcquired // samplesAcquiredFcnCount
            self.timerPeriod = 0.0001 # in sec
            self.timer = rptTimer(self.timerPeriod,self._update, autodt = False, verbose = False)
            self.trigArmed = True # arm trig if curidx keeps the same for trigWatchCount points
            self.timeLastTrig = None # for AI trigFcn. It's time.time() of the last trigger event
            self.timeThreshold = None # arm trigger again if the elapsed time after the prior trigger is longer than this expected trigger period
            self.aicuridx = None # for arming AI trigger

        def _execute(self,fcnset,eventdata): # call the function
            # arg = ()
            # kwarg = {}
            # try:
            #     if fcnset[1]:
            #         arg = fcnset[1]
            # except:
            #     pass
            # try:
            #     if fcnset[2]:
            #         kwarg = fcnset[2]
            # except:
            #     pass
            # if callable(fcnset[0]):
            #     try:
            #         fcnset[0](eventdata,*arg,**kwarg)
            #     except:
            #         print('Example callback definition: foo(eventdata,*args,**kwargs) or foo(self,eventdata,*args,**kwargs) if it is a member function.')
            #         traceback.print_exc()
            # else:
            #     print(f'{fcnset[0]} is not callable')
            try:
                fcnset(eventdata)
            except:
                print(f'Error calling {eventdata.event} callback function')
                traceback.print_exc()


        def _update(self): # updating status
            if self.daq.ai:
                '''
                Note: if AI is in foreground mode, none of the AI callback will be executed since it blocks
                    code execution during acquisition
                '''
                status, _, curidx = ul.get_status(self.daq.daqid,FunctionType.AIFUNCTION)
                curtime = time.time()
                if not self.timeLastTrig: # listener just started
                    self.timeLastTrig = curtime

                if ((not self.trigArmed) and (self.timeThreshold) and (self.aicuridx == curidx) and 
                    ((curtime - self.timeLastTrig) > self.timeThreshold)):
                    self.trigArmed = True
                    
                if self.aicuridx != curidx:
                    self.aicuridx = curidx
                    if self.trigArmed:
                        self.trigArmed = False
                        self.timeLastTrig = curtime
                        self.daq.ai._trigTime.append(curtime)
                        if self.daq.ai.trigFcn:
                            self._execute(self.daq.ai.trigFcn,{'time':curtime,'event':'AItrigFcn'})

                if self.aistatus != status:
                    self.aistatus = status
                    if self.daq.ai.startFcn and (status == Status.RUNNING):
                        self._execute(self.daq.ai.startFcn,{'time':curtime,'event':'AIstartFcn'})
                    elif self.daq.ai.stopFcn and (status == Status.IDLE):
                        self._execute(self.daq.ai.stopFcn,{'time':curtime,'event':'AIstopFcn'})

                if self.daq.ai.samplesAcquiredFcn and (self.daq.ai.samplesAcquiredFcnCount != 0):
                    quotient = self.daq.ai.samplesAcquired // self.daq.ai.samplesAcquiredFcnCount
                    if quotient > self.samplesAcquiredQuotient:
                        self.samplesAcquiredQuotient = quotient
                        self._execute(self.daq.ai.samplesAcquiredFcn,{'time':curtime,'event':'samplesAcquiredFcn',
                                                                      'samplesAcquired':self.daq.ai.samplesAcquired})

            if self.daq.ao:
                status, _, _ = ul.get_status(self.daq.daqid,FunctionType.AOFUNCTION)
                if self.aostatus != status:
                    self.aostatus = status
                    if self.daq.ao.startFcn and (status == Status.RUNNING):
                        self._execute(self.daq.ao.startFcn,{'time':curtime,'event':'AOstartFcn'})
                    elif self.daq.ao.stopFcn and (status == Status.IDLE):
                        self._execute(self.daq.ao.stopFcn,{'time':curtime,'event':'AOstopFcn'})

        def start(self): # listener start
            if self.islistening: # started by AI or AO already
                return
            
            self.samplesAcquiredQuotient = 0
            if self.daq.ao:
                self.aostatus, _, _ = ul.get_status(self.daq.daqid,FunctionType.AOFUNCTION)
            if self.daq.ai:
                self.aistatus, _, self.aicuridx = ul.get_status(self.daq.daqid,FunctionType.AIFUNCTION)
                self.trigArmed = True # arm trig if curidx keeps the same for trigWatchCount points
                self.timeLastTrig = None # for AI trigFcn. It's time.time() of the last trigger event
                #self.timeThreshold = 512/self.daq.ai.sampleRate # Typical half-FIFO sizes are 256, 512 and 1,024 <- this is not reliable 
                if (self.daq.ai.trigRepeat == 1):
                    self.timeThreshold = None
                else:
                    self.timeThreshold = self.daq.ai.samplesPerTrig / self.daq.ai.sampleRate
                        
            

            self.islistening = True    
            self.timer.start()

        def stop(self): # listener stop
            aistatus = aostatus = None
            if self.daq.ao:
                aostatus, _, _ = ul.get_status(self.daq.daqid,FunctionType.AOFUNCTION)
            if self.daq.ai:
                aistatus, _, _ = ul.get_status(self.daq.daqid,FunctionType.AIFUNCTION)
            if (aistatus == Status.RUNNING) or (aostatus == Status.RUNNING):
                return # AI or AO is still running
            else:
                self.timer.stop()
                self.islistening = False

            if ((self.daq.ao and (self.aostatus != aostatus)) or
                (self.daq.ai and (self.aistatus != aistatus))):
                self._update() # enure the last callback is executed


# %% [markdown]
# #### mcc_ao

# %%
# mcc AO class definition ------------------------------------------------------------------------
class mcc_ao(aoBase):
    def __init__(self, daq, lowCh, highCh, **kwarg):
        # Copy docstring from the parent class for the methods
        for method in getMethods(mcc_ao):
            exec(f'mcc_ao.{method}.__doc__ = aoBase.{method}.__doc__')

        # Initialization tasks
        super().__init__(daq, lowCh, highCh, **kwarg)
        self.range = self.info.supported_ranges[0] # ULRange.BIP10VOLTS  # Output range +/- 10V
        self.scanoption = (ScanOptions.CONTINUOUS | ScanOptions.BACKGROUND) # only support this mode for now

    def _assertVariable(self):
        super()._assertVariable()
        # Add additional variables below if needed
        assert len(self.data) > 0, 'Nothing to output. Assign voltage data using \'ao.putdata(numpy.ndarray)\' first.'

    def start(self): # AO start
        if self.isrunning:
            print('AO is running already')
            return
        self._assertVariable()

        try:
            self.daq.eventlistener.start()
            self.isrunning = True
            ul.a_out_scan(
                self.daq.daqid,         # Board number
                self.channel[0],    # Start channel
                self.channel[1],    # End channel (same as start for single channel)
                len(self.data),     # Number total samples
                self.sampleRate,    # Rate of the scan
                self.range,         # Range for the output
                self.data.ctypes.data_as(ctypes.POINTER(ctypes.c_uint16)),  # The data buffer (converted to ctypes)
                self.scanoption
            )
        except ul.ULError as e:
            print("A ULError occurred. Code:", e.errorcode)
            print("Check error code at: https://files.digilent.com/manuals/Mcculw_WebHelp/ULStart.htm")
            traceback.print_exc()

    def stop(self): # AO stop
        if not self.isrunning:
            print('AO has already stopped')
            return
        ul.stop_background(self.daq.daqid, FunctionType.AOFUNCTION)
        if self.endMode == 'hold':
            pass
        elif self.endMode == 'zero':
            #self.putvalue(np.zeros(self.channel[1] - self.channel[0] + 1))
            for ch in range(self.channel[0],self.channel[1]+1):
                ul.a_out(self.daq.daqid, ch, self.range, ul.from_eng_units(self.daq.daqid, self.range, 0))
        self.isrunning = False
        self.daq.eventlistener.stop()
        
    def putvalue(self,voltage):
        if self.isrunning:
            print('AO is still running. putvalue() aborted')
            return
        self.isrunning = True
        Nch = self.channel[1] - self.channel[0] + 1
        assert len(voltage) == Nch, f'len(voltage) must be equal to the number of channels: {Nch}'
        for i,ch in enumerate(range(self.channel[0],self.channel[0]+Nch)):
            ul.a_out(self.daq.daqid, ch, self.range, ul.from_eng_units(self.daq.daqid, self.range, voltage[i]))
        self.isrunning = False
        
    def putdata(self,voltage):
        if self.isrunning:
            print('AO is still running. putdata() aborted')
            return
        assert type(voltage) == np.ndarray, 'Output data must be a numpy ndarray'
        voltage = voltage.reshape(-1,order = 'F') # convert to 1D scan sequence
        # convert to np.array so I don't need to worry about casting and memory management
        self.data = np.array([ul.from_eng_units(self.daq.daqid, self.range, voltage[i]) for i in range(len(voltage))], dtype = np.uint16)



# %% [markdown]
# #### mcc_ai

# %%
# mcc AI class definition ------------------------------------------------------------------------
class mcc_ai(aiBase):
    set_grounding = {'single-ended': AnalogInputMode.SINGLE_ENDED,
                     'grounded': AnalogInputMode.GROUNDED,
                     'differential': AnalogInputMode.DIFFERENTIAL} #cannot be defined in the inner class...
    set_trigType = {'instant': None,
                    'digital-positive-edge': TrigType.TRIG_POS_EDGE}
    set_aqMode = {'foreground': ScanOptions.FOREGROUND,
                  'background':ScanOptions.BACKGROUND}
    
    def __init__(self, daq, lowCh, highCh, **kwarg):
        # Copy docstring from the parent class for the methods
        for method in getMethods(mcc_ai):
            exec(f'mcc_ai.{method}.__doc__ = aiBase.{method}.__doc__')

        # Initialization tasks
        super().__init__(daq, lowCh, highCh, **kwarg)
        self.range = self.info.supported_ranges[0] # ULRange.BIP10VOLTS  # Output range +/- 10V
        self.scanoption = ScanOptions.FOREGROUND # 0x0000 it means the default setting for everything
        self.istransferring = False # is getdata() transferring data
        self.bufferSize = None # for all channels; calculated at _dataBroker.start()
        self.buffer = None # circular buffer
        self._broker = None # manage memory and streaming data
        self._Nch = self.channel[1] - self.channel[0] + 1 # total number of channels

        # for dev only. This allows me to program without the physical board.
        if self.range == ULRange.NOTUSED:
            self.demo = True # cannot set grounding and trigger type
        else:
            self.demo = False
        
    def _assertVariable(self):
        super()._assertVariable()
        # Add additional variables below if needed
        
    # # Define the Python event handler for end of scan
    # @ul.ULEventCallback
    # def endOfScanFcn(board_num, event_type, event_data, cvar):
    #     '''
    #     * Call self.stop() after the scan finishes under non-continuous or foreground modes
    #     * It won't be called after issuing stop_background()
    #     '''
    #     # self = ctypes.cast(cvar, ctypes.py_object).value # still doesn't work...
    #     # self.stop(self)
    #     print('Foreground acquisition is done')
        
    class _dataBroker():
        '''
        This inner class does the followings:
        * determines win buffer size and manage the memory
        * extracts data from win circular buffer and puts them in outer.data continuously
        * serves as a persistent variable space
        '''
        def __init__(self,ai):
            self.ai = ai
            self.timer = None # threading.Timer object
            self.timerPeriod = None # in sec
            self.autodt = False # adjut timer period automatically
            self.istransferring = False # is extractdata() transferring data
            self.startidx = 0 # start index of the win buffer to be transferred
            self.endidx = None # end index (i.e. end point+1) of the win buffer to be transferred
            self.array = None # = ctypes.cast(self.ai.buffer, ctypes.POINTER(ctypes.c_ushort))
            self.reset = True # this will reset self.startidx to 0. Set to True in ai.start()
            
        def __del__(self):
            try:
                self.stop() # make sure to release the memory
            except:
                pass # when the memory has been released normally etc.

        def copydata(self,start,end):
            return [ul.to_eng_units(self.ai.daq.daqid, self.ai.range, self.array[i]) for i in range(start,end,self.ai._Nch)]
            
        def extractdata(self,*arg,**kwarg):
            '''
            From the user manual of get.status():
            cur_index (int) – The cur_index value is an index into the Windows data buffer.
            This index points to the start of the last completed channel scan that was 
            transferred between the DAQ board and the Windows data buffer. If no points in
            the buffer have been transferred, cur_index equals –1 in most cases.
            
            For CONTINUOUS operations, cur_index rolls over when the Windows data buffer is
            full. This rollover indicates that "new" data is now overwriting "old" data. 
            Your goal is to process the old data before it gets overwritten. You can keep 
            ahead of the data flow by copying the old data out of the buffer before new data
            overwrites it.
            
            The cur_index value can help you access the most recently transferred data. Your
            application does not have to process the data exactly when it becomes available 
            in the buffer - in fact, you should avoid doing so unless absolutely necessary. 
            The cur_index parameter generally increments by the packet size, but in some 
            cases the cur_index increment can vary within the same scan. One instance of a 
            variable increment is when the packet size is not evenly divisible by the number
            of channels. You should determine the best size of the "chunks" of data that your
            application can most efficiently process, and then periodically check on the 
            cur_index parameter value to determine when that amount of additional data has 
            been transferred. Refer to board-specific information for specific information 
            about your board, particularly when using pre-trigger.

            TMW Note: curidx from ul.get_status() won't be reset to -1 again when starting the 2nd time
                unless the Python kernel is reset.
            '''
            # curidx + self.ai._Nch is the actual (end point + 1) of the data transferred from DAQ to win buffer
            _, _, curidx = ul.get_status(self.ai.daq.daqid,FunctionType.AIFUNCTION)
            #status, curcount, curidx = ul.get_status(self.ai.daq.daqid,FunctionType.AIFUNCTION)
            #print(f'status = {status}; curidx = {curidx}; startidx = {self.startidx}; endidx = {self.endidx}')

            if self.reset or (self.endidx == curidx + self.ai._Nch): # no new data in the buffer
                #print(f'Waiting for data in _dataBroker. curidx = {curidx}; startidx = {self.startidx}; endidx = {self.endidx}')
                # instant trigger will only enter here once after the acquisition is done if extractdata() is used!!
                if self.reset:
                    self.startidx = 0
                    self.endidx = curidx + self.ai._Nch
                    self.reset = False
            else:
                count = 0 # number of samples/channel extracted this time
                self.endidx = curidx + self.ai._Nch
                #print(f'curidx = {curidx}; startidx = {self.startidx}; endidx = {self.endidx}')
                if self.ai.istransferring: # if ai.getdata() is extracting data
                    print('Waiting for ai.getdata() to complete.') # wait for the transfer to complete
                    while self.ai.istransferring:
                        time.sleep(0.005)
                
                try:
                    self.istransferring = True
                    if self.startidx < self.endidx:
                        # Normal circumstance
                        for ch in range(self.ai._Nch):
                            self.ai.data[ch].extend(
                                #[ul.to_eng_units(self.ai.daqid, self.ai.range, self.array[i]) for i in range(self.startidx+ch,self.endidx,self.ai._Nch)]
                                self.copydata(self.startidx+ch,self.endidx)
                            ) #append data to each channel
                        count = self.endidx - self.startidx
                    else:
                        # the circular buffer was full and has wrapped around
                        for ch in range(self.ai._Nch):
                            self.ai.data[ch].extend(
                                #[ul.to_eng_units(self.ai.daqid, self.ai.range, self.array[i]) for i in range(self.startidx+ch,self.ai.bufferSize,self.ai._Nch)]
                                self.copydata(self.startidx+ch,self.ai.bufferSize)
                            ) # extract to the end of the buffer
                            self.ai.data[ch].extend(
                                #[ul.to_eng_units(self.ai.daqid, self.ai.range, self.array[i]) for i in range(ch,self.endidx,self.ai._Nch)]
                                self.copydata(ch,self.endidx)
                            ) # extract the wrapped around part
                        count = (self.ai.bufferSize - self.startidx) + (self.endidx)

                    self.startidx = self.endidx
                    self.ai.samplesAcquired += int(count/self.ai._Nch)
                    self.istransferring = False
                    #print(f'self.ai.samplesAcquired = {self.ai.samplesAcquired}, cur_count/Nch = {int(curcount/self.ai._Nch)}, curidx/Nch = {int(curidx/self.ai._Nch)}')
                except:
                    print('Something is wrong when transferring data in _dataBroker.extractdata')
                    self.istransferring = False
                    traceback.print_exc()
                    self.stop()
                    
        def start(self): # dataBroker start
            '''
            start monitoring and transferring data
            '''
            
            # Determine buffer size and allocate memory
            # if self.ai.iscontinuous:
            #     if self.ai.trigType == 'instant':
            #         self.ai.bufferSize = int(self.ai.sampleRate * self.ai._Nch) # 1 sec buffer capacity
            #     else: # Inf trigger
            #         self.ai.bufferSize = self.ai.samplesPerTrig * self.ai._Nch # AI overwrites the buffer everytime; each trigger acquires bufferSize of samples
            # else:
            #     self.ai.bufferSize = self.ai.samplesPerTrig * self.ai.trigRepeat * self.ai._Nch # must be able to contain all data

            #TW20250127 - Change the logic of how the bufferSize is determined
            if self.ai.iscontinuous:
                if self.ai.trigRepeat == 1:
                    self.ai.bufferSize = int(self.ai.sampleRate * self.ai._Nch) # 1 sec buffer capacity
                else: # Inf trigger
                    # Ensure the buffer is large enough to hold > 1 sec of fast trigger data
                    self.ai.bufferSize = ceil(self.ai.sampleRate//self.ai.samplesPerTrig) * self.ai.samplesPerTrig * self.ai._Nch
            else:
                self.ai.bufferSize = self.ai.samplesPerTrig * self.ai.trigRepeat * self.ai._Nch # must be able to contain all data
  
            # Allocate memory
            #print(f'bifferSize = {self.ai.bufferSize}')
            self.ai.buffer = ul.win_buf_alloc(self.ai.bufferSize)
            self.array = ctypes.cast(self.ai.buffer, ctypes.POINTER(ctypes.c_ushort)) # for self.extractdata
            
            # Set up timer
            # if self.ai.bufferSize/self.ai._Nch/self.ai.sampleRate < 1: # if each trigger period is <1 sec
            #     self.timerPeriod = self.ai.samplesPerTrig/self.ai.sampleRate/5 #check 5 times per trigger
            #     if self.timerPeriod < 0.1:
            #         self.timerPeriod = 0.1 #minimal timer period
            # else:
            #     self.timerPeriod = 0.2

            self.timerPeriod = 0.2
            
            try:
                if self.ai.aqMode == 'background': # cannot extract data during foreground acquisition anyway
                    self.timer = rptTimer(self.timerPeriod, self.extractdata, autodt = self.autodt)
                    self.timer.start()
                
            except Exception:
                print('Something is wrong when starting _dataBroker timer')
                self.istransferring = False
                traceback.print_exc()
                self.stop()
        
        def stop(self): # dataBroker stop
            '''
            ensure final data transfer and release the memory
            '''
            if self.istransferring:
                print('Waiting for data transfer in _dataBroker to complete.')
                while self.istransferring:
                    time.sleep(0.01)

            if self.ai.aqMode == 'background':
                self.timer.stop()
            else: # foreground
                # self.extractdata() is not designed for foreground acquisition
                for ch in range(self.ai._Nch):
                    self.ai.data[ch] = self.copydata(ch,self.ai.bufferSize)
                
            ul.win_buf_free(self.ai.buffer) # release memory
            print('win buffer freed')
        
    def start(self): # AI start
        if self.isrunning:
            print('AI is running already')
            return
        self._assertVariable()
        
        # Set grounding type
        if self.demo:
            print('\033[33mDemo board does not support grounding type setting -> skip\033[0m')
        else:
            ul.a_input_mode(self.daq.daqid, mcc_ai.set_grounding[self.grounding])
        
        # Reset everything to default i.e. 0x0000
        self.scanoption = ScanOptions.FOREGROUND # 0x0000 it means the default setting for everything

        # Set acquisition mode
        self.scanoption |= mcc_ai.set_aqMode[self.aqMode]
        
        # Set / configure trigger
        if self.demo and (self.trigType != 'instant'):
            self.trigType = 'instant'
            print('\033[33mDemo board only supports instant trigger -> corrected\033[0m')
            
        # if self.trigType != 'instant':
        #     self.scanoption |= (ScanOptions.EXTTRIGGER)
        #     if (self.trigRepeat > 1) or (self.iscontinuous):
        #         self.scanoption |= ScanOptions.RETRIGMODE

        #     ul.set_trigger(self.daq.daqid, self.set_trigType[self.trigType], 0, 0) # set_trigger(board_num, trig_type, low_threshold, high_threshold)
            
        #     if self.iscontinuous: # Inf trigger counts
        #         ul.set_config(InfoType.BOARDINFO, self.daq.daqid, 0, BoardInfo.ADTRIGCOUNT, 0) #overwrite/refill the buffer with every trigger
        #         if self.aqMode == 'foreground':
        #             self.aqMode = 'background'
        #             print(f'\033[33mForeground mode is not allowed for multiple triggers -> changed to Background mode\033[0m')        
        #     else:
        #         if (self.aqMode == 'foreground') and (self.trigRepeat > 1):
        #             self.aqMode = 'background'
        #             print(f'\033[33mForeground mode is not allowed for multiple triggers -> changed to Background mode\033[0m')
        #         ul.set_config(InfoType.BOARDINFO, self.daq.daqid, 0, BoardInfo.ADTRIGCOUNT, self.samplesPerTrig * self._Nch) # acquire aiSR*duration*Nch samples with each trigger

        # if self.iscontinuous:
        #     self.scanoption |= ScanOptions.CONTINUOUS
        #     if self.trigRepeat > 1:
        #         print(f'\033[33mtrigRepeat is ignored in Continuous mode\033[0m')
        #     if self.aqMode == 'foreground':
        #         self.aqMode = 'background'
        #         print(f'\033[33mForeground mode is not allowed for continuous acquisition -> changed to Background mode\033[0m')

        # TW20250126 - Change the logic of how the scanoption is determined
        if self.trigType != 'instant':
            self.scanoption |= (ScanOptions.EXTTRIGGER)
            ul.set_trigger(self.daq.daqid, self.set_trigType[self.trigType], 0, 0) # set_trigger(board_num, trig_type, low_threshold, high_threshold)

        if self.iscontinuous: # self.trigRepeat = 1 or 'inf'
            self.scanoption |= ScanOptions.CONTINUOUS
            if self.trigRepeat == 1: # one trigger, continuous acquisition
                self.samplesPerTrig = 'inf'
            elif self.trigRepeat in ['inf','Inf']: # inf triggers
                self.scanoption |= ScanOptions.RETRIGMODE
                ul.set_config(InfoType.BOARDINFO, self.daq.daqid, 0, BoardInfo.ADTRIGCOUNT, 0) #overwrite/refill the buffer with every trigger
                
            else: # raise error message
                raise ValueError(f'ai.trigRepeat can only be 1 or "inf" when ai.iscontinuous == True. It is {self.trigRepeat} now.')

            if self.aqMode == 'foreground':
                self.aqMode = 'background'
                print(f'\033[33mForeground mode is not allowed when ai.iscontinuous == True -> changed to Background mode\033[0m')

        else: #self.trigRepeat must be >=1 integer
            if self.trigRepeat > 1:
                self.scanoption |= ScanOptions.RETRIGMODE
                ul.set_config(InfoType.BOARDINFO, self.daq.daqid, 0, BoardInfo.ADTRIGCOUNT, self.samplesPerTrig * self._Nch) # acquire aiSR*duration*Nch samples with each trigger

        if (self.trigRepeat != 1) and (self.samplesPerTrig in ['inf','Inf']):
            # self.samplesPerTrig = 1000
            # print(f'\033[33mai.samplesPerTrig cannot be \'inf\' when ai.trigRepeat > 1 -> changed to {self.samplesPerTrig}\033[0m')
            raise ValueError(f'ai.samplesPerTrig cannot be "inf" when ai.trigRepeat > 1.')
            
        if self.aqMode == 'background':
            self.scanoption |= ScanOptions.BACKGROUND
        
        # Prep empty self.data list etc. for data storage in self._broker.extractdata()
        self.data = [[] for _ in range(self._Nch)] # use list instead of numpy array because appending data to numpy array is inefficient
        #self.aitime = []
        self.samplesAcquired = 0 # number of samples/channel transferred to ai.data
        self._nextdataidx = 0 # for aitime generation. It's the index (i.e. number of total transferred samples) to the 1st data point of the NEXT getdata() event. It will be updated in getdata()
        self._trigTime = [] # for aitime generation
        
        # Start acquitision
        self._broker = self._dataBroker(self) # Set up data broker for memory allocation and data extraction
        self._broker.reset = True
        self._broker.start() # start transferring data; _broker has its own try-except clause
        self.daq.eventlistener.start()
        try:
            self.isrunning = True
            ul.a_in_scan(
                self.daq.daqid,      # Board number
                self.channel[0],     # Start channel
                self.channel[1],     # End channel (same as start for single channel)
                self.bufferSize,     # Number total samples
                self.sampleRate,     # Rate of the scan
                self.range,          # Range for the output
                self.buffer,         # allocated by ul.win_buf_alloc() directly
                self.scanoption 
            )
            
        except ul.ULError as e:
            print("A ULError occurred. Code:", e.errorcode)
            print("Check error code at: https://files.digilent.com/manuals/Mcculw_WebHelp/ULStart.htm")
            traceback.print_exc()
            #ul.disable_event(self.daqid, EventType.ALL_EVENT_TYPES)
        finally:
            if self.aqMode == 'foreground':
                # without the 'if', acquisition will be stopped immediately in background mode
                self.stop()

    def stop(self): # AI stop
        if not self.isrunning:
            print('AI has already stopped')
            return
        print('Acquisition is done')
        self._broker.stop()
        if self.aqMode == 'background':
            ul.stop_background(self.daq.daqid, FunctionType.AIFUNCTION)
        self.isrunning = False
        self.daq.eventlistener.stop()
        #ul.disable_event(self.daq.daqid, EventType.ALL_EVENT_TYPES)
        
    def getvalue(self):
        if self.isrunning:
            print('AI is still running. getvalue() aborted')
            return
        self.isrunning = True
        Nch = self.channel[1] - self.channel[0] + 1
        data = []
        for ch in range(self.channel[0],self.channel[0]+Nch):
            data.append(ul.to_eng_units(self.daq.daqid, self.range, 
                                        ul.a_in(self.daq.daqid, ch, self.range)))
        self.isrunning = False
        return data #TODO - verify data -> something could be wrong in a_in() itself
        
    def getdata(self,*arg,to_numpy=True):
        Narg = len(arg)
        assert Narg <= 1, f'ai.getdata() accepts zero or one input argument. It is {Narg} now.'
        if self._broker.istransferring: # if dataBroker is transferring data
            print('Waiting for data transfer from memory to complete.') # wait for the transfer to complete
            while self._broker.istransferring: # if dataBroker is transferring data
                time.sleep(0.005)

        self.istransferring = True
        Navb = len(self.data[0]) # number of available samples
        if Narg == 1:
            if arg[0] > Navb:
                print(f'The requested number of data exceeds the number of available data. All available {Nreq} samples will be returned')
                Nreq = Navb
            else:
                Nreq = arg[0]
        else:
            Nreq = Navb
            
        data = [[] for _ in range(self._Nch)]
        aitime = []
        # Extract data
        for ch in range(self._Nch):
            data[ch].extend(self.data[ch][0:Nreq]) #copy data from the engine
            del self.data[ch][0:Nreq] #remove extracted data from the engine

        # Generate aitime TODO - handle missed trigger events
        if self.trigRepeat == 1: # don't need to consider gaps between triggers
            aitime = [(self._nextdataidx + n) / self.sampleRate for n in range(Nreq)]
            self._nextdataidx += Nreq
        else:
            starttrig = self._nextdataidx // self.samplesPerTrig # zero-based
            endtrig = ceil((self._nextdataidx + Nreq) / self.samplesPerTrig) # endtrig won't be reached
            #print(f'starttrig:{starttrig} endtrig:{endtrig}')
            for trigidx in range(starttrig,endtrig):
                startidx = self._nextdataidx % self.samplesPerTrig
                if (startidx + Nreq) <= self.samplesPerTrig: # N of requested points are within a trigger
                    endidx = startidx + Nreq # endidx wont'e be reached. The idx of the last point is endidx-1.
                else:
                    endidx = self.samplesPerTrig # point to the start of the next trigger
                aitime.extend([self._trigTime[trigidx] - self._trigTime[0] + (n / self.sampleRate) for n in range(startidx,endidx)])
                count = endidx - startidx
                Nreq -= count
                self._nextdataidx += count
                #print(f'trigidx:{trigidx} startidx:{startidx} endidx:{endidx} _nextdataidx:{self._nextdataidx}')
        if to_numpy:
            aitime = np.array(aitime)
            data = np.array(data)

        self.istransferring = False
        return aitime, data

