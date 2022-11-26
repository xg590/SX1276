from machine import Pin 
import time, urandom as random
from lora import SX1276

# Heltec WiFi LoRa 32 V2
LoRa_MISO_Pin = 19
LoRa_MOSI_Pin = 27
LoRa_SCK_Pin  =  5
LoRa_CS_Pin   = 18
LoRa_RST_Pin  = 14
LoRa_DIO0_Pin = 26
LoRa_DIO1_Pin = 35
LoRa_DIO2_Pin = 34
SPI_CH        =  1 

random.seed(11)   
channels2Hopping = [914_000_000+200_000 * random.randint(0,10) for i in range(128)] # Both sender and receiver need to know the sequence of frequences they are hopping on before the first hopping operation.

LoRa_id = 0
lora = SX1276(LoRa_RST_Pin, LoRa_CS_Pin, SPI_CH, LoRa_SCK_Pin, LoRa_MOSI_Pin, LoRa_MISO_Pin, LoRa_DIO0_Pin, LoRa_DIO1_Pin, LoRa_id, channels2Hopping)
#lora.after_TxDone = lambda self, _: print('TxDone')
lora.req_packet_handler = lambda self, packet, SNR, RSSI: print("[New 'REQ' packet]", packet, SNR, RSSI)
lora.brd_packet_handler = lambda self, packet, SNR, RSSI: print("[New 'BRD' packet]", packet, SNR, RSSI)  
lora.mode = 'RXCONTINUOUS'