from machine import Pin
from lora import SX1276
import time, urandom

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

 
urandom.seed(11)   
channels2Hopping = [902_300_000+200_000 * urandom.randint(0,127) for i in range(128)] # 902~928 MHz  

LoRa_id = 0
lora = SX1276(LoRa_RST_Pin, LoRa_CS_Pin, SPI_CH, LoRa_SCK_Pin, LoRa_MOSI_Pin, LoRa_MISO_Pin, LoRa_DIO0_Pin, LoRa_DIO1_Pin, LoRa_id, channels2Hopping)
lora.after_TxDone   = lambda self: print('TxDone')
lora.req_packet_handler = lambda self, packet, SNR, RSSI: print('New req packet:', packet, SNR, RSSI)
lora.brd_packet_handler = lambda self, packet, SNR, RSSI: print('New brd packet:', packet, SNR, RSSI)
lora.mode = 'RXCONTINUOUS'