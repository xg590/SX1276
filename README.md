## SX1276
MicroPython Library for SX1276 LoRa radio modem 
## Features 
* Send request, ask for response from a specified recipient, and broadcast. 
* Implement FHSS (first?)
  * FCC mandates freqyency hopping if dwell time is above the threshold 400ms.  
  * Large spreading factor and narrow bandwidth can significantly prolong the dwell time so that freq hopping is necessary for transmiiting large packet.
## My dev environment
* Two ESP32 with SX1276 (Heltec WiFi LoRa 32 V2)
* VScode with Pico-Go extension 
* I configured project and global settings <i>pico-go.json</i> for Pico-Go ext so I can open two VScode window/instances and connect to two ESP32 boards simultanously
## Usage
* Connect two boards to dev machine
* Open sender and receiver folders in two separate VScode windows.
* Upload lora.py to boards 
* Run sender.py and receiver.py
## Note
* It is meaningless to do Channel Activity Detection (CAD) before Tx because SX1276 only match elusive preambles which last few milliseconds. No good solution to do Listen Before Talk or CSMA. 
