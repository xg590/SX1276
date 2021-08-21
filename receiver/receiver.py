from machine import Pin
from lora import SX1276
import time, urandom

# RFM95W         Pico GPIO old
LoRa_MISO_Pin  = 16
LoRa_CS_Pin    = 17
LoRa_SCK_Pin   = 18
LoRa_MOSI_Pin  = 19
LoRa_G0_Pin    = 20 # DIO0_Pin
LoRa_EN_Pin    = 21
LoRa_RST_Pin   = 22
SPI_CH         =  0

Pin(LoRa_EN_Pin, Pin.OUT).on()
LoRa_id = 0
lora = SX1276(LoRa_RST_Pin, LoRa_CS_Pin, SPI_CH, LoRa_SCK_Pin, LoRa_MOSI_Pin, LoRa_MISO_Pin, LoRa_G0_Pin, LoRa_id)
lora.after_TxDone   = lambda self: print('TxDone')
lora.req_packet_handler = lambda self, packet, SNR, RSSI: print('New req packet:', packet, SNR, RSSI)
lora.brd_packet_handler = lambda self, packet, SNR, RSSI: print('New brd packet:', packet, SNR, RSSI)
lora.mode = 'RXCONTINUOUS'