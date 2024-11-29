![License](https://img.shields.io/badge/license-MIT-blue)
# daqx
:warning: This project is still under construction / development

Python data acquisition toolbox - Wrapper that provides high-level layers for controlling data acquisition boards. It also handles low-level memory management, data transfer, and provides various types of event callbacks.

Currently, it only supports boards from Measurement Computing. Support for National Instruments may be added in the future.

## Table of Contents
- [Installation](#installation)
- [Event Callbacks](#event-callbacks)
- [Usage](#usage)

## Installation
- `pip install daqx`

## Event Callbacks
**Start callback -** AI, AO

**Stop callback -** AI, AO

**Trigger callback -** AI

**Samples acquired callback -** AI

## Usage
```python
from daqx.util import createDevice

daqid = 0
start_channel = 0                           # start scanning at channel 0
end_channel = 1                             # end scanning at channel 1
daq = createDevice('mcc',daqid)             # only 'mcc', Measurement Computing is supported currently
daq.config_ai(start_channel,end_channel)    # set up analog input

daq.ai.sampleRate = 1000                    # Hz/channel
daq.ai.grounding = 'single-ended'           # Support 'single-ended','grounded','differential'
daq.ai.trigType = 'instant'                 # support 'instant','digital-positive-edge'
daq.ai.samplesPerTrig = 2000                # Samples/channel/trigger
daq.ai.aqMode = 'foreground'                # acquisition mode - 'foreground','background'

daq.ai.start()
# after 2 seconds
aitime, aidata = daq.ai.getdata()

```
Tutorial will be added in the future.

