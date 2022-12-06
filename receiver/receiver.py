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
lora = SX1276(LoRa_RST_Pin, LoRa_CS_Pin, SPI_CH, LoRa_SCK_Pin, LoRa_MOSI_Pin, LoRa_MISO_Pin,
              LoRa_DIO0_Pin, LoRa_DIO1_Pin, LoRa_id, channels2Hopping, debug=False)

def get_payload(self, data, SNR, RSSI):
    global received_payload
    received_payload = data

lora.req_packet_handler = get_payload
lora.brd_packet_handler = lambda self, data, SNR, RSSI: print("[BRD]", data)

###########################################
#                                         #
#   Prepare to receive first REQ packet   #
#                                         #
###########################################

received_payload = None
lora.mode = 'RXCONTINUOUS'
while not lora.is_available:
    time.sleep(1)
print("[Note] We will see this line after receiver ACKed the first REQ packet with an ACK packet. And the receiver will stop listening, become a new sender, and send a REQ packet to the old sender (new receiver).")

######################################################################
#                                                                    #
#   if we receive the hello packet correctly, we reply it with Hi.   #
#                                                                    #
######################################################################
# if we fail, nothing will go further
print('[Received]', received_payload)
if received_payload[-6:] != b'Hello~': raise

payload = str(random.randint(100,65536))+") Hi ~ I have received your hello"
lora.send(dst_id=1, msg=payload, pkt_type=lora.PKT_TYPE['REQ'])
print('[Sending]', payload)
while not lora.is_available: # Stop if our reply got acknowledged.
    time.sleep(1)

##########################################
#                                        #
#   Prepare to receive two BRD packets   #
#                                        #
##########################################

received_payload = None
lora.mode = 'RXCONTINUOUS'

while not lora.is_available:
    #print("waiting")
    time.sleep(1)

print("[Note] This line will not be reached because BRD is not two-way communication. The receiver will not stop listening")