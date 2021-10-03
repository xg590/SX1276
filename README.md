## SX1276
MicroPython Library for SX1276 
## Features
* Send request for acknowledgement and wait 15 seconds for response.
* Send request but specify a wrong receiver id so acknowledgement will not succeed.
* Send broadcast and wait no time
## My dev environment
* Two Raspberry Pi Pico boards and two Adafruit RFM95W breakouts
* VScode with Pico-Go extension 
* I configured project and global settings <i>pico-go.json</i> for Pico-Go ext so I can open two VScode window/instances and connect to two Pico boards simultanously
## Usage
* Connect two boards to dev machine
* Open sender and receiver folders in two separate VScode windows.
* Upload lora.py to boards 
* Run sender.py and receiver.py
## To-do List
* It is meaningless to do Channel Activity Detection (CAD) before Tx because SX1276 only match elusive preambles which last few milliseconds. No good solution to do Listen Before Talk or CSMA.
* FHSS implementation
  * FCC mandates freq hopping if dwell time is above a threshold. 
  * Found sample code [here](https://os.mbed.com/teams/Semtech/code/SX1276PingPongFHSS/)
