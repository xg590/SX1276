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
channels2Hopping = [914_000_000+200_000 * random.randint(0,10) for i in range(128)] # 914~916 MHz

LoRa_id = 1
lora = SX1276(LoRa_RST_Pin, LoRa_CS_Pin, SPI_CH, LoRa_SCK_Pin, LoRa_MOSI_Pin, LoRa_MISO_Pin,
              LoRa_DIO0_Pin, LoRa_DIO1_Pin, LoRa_id, channels2Hopping, debug=False)

def get_payload(self, data, SNR, RSSI):
    global received_payload
    received_payload = data

lora.req_packet_handler = get_payload

###########################################
#                                         #
#             First REQ packet            #
#                                         #
###########################################

payload = str(random.randint(100,65536))+") Hello~"
print('[Sending]', payload)
lora.send(dst_id=0, msg=payload, pkt_type=lora.PKT_TYPE['REQ']) # Sender's lora_id is 1 and receiver's is 0
while not lora.is_available: time.sleep(1)

#####################################################
#                                                   #
#   Going to receive a Hi. Two way communication~   #
#                                                   #
#####################################################

received_payload = None
lora.mode = 'RXCONTINUOUS'

while not lora.is_available:
    time.sleep(1)

print('[Received] What we receive from the receiver is:', received_payload)

#######################################################
#                                                     #
#   Send a REQ packet but specify a wrong receiver    #
#                                                     #
#######################################################

payload = str(random.randint(100,65536))+") You will not receive this packet because we specified a wrong dst_id"
print('[Sending]', payload)
lora.send(dst_id=3, msg=payload, pkt_type=lora.PKT_TYPE['REQ'], timeout=10, retry=3, debug=True)

for i in range(10):
    if lora.is_available: break
    time.sleep(1)
else:
    print("[Note] you will see this line because lora.is_available is always false")

############################
#                          #
#   Send two BRD packets   #
#                          #
############################

time.sleep(10)
payload = str(random.randint(100,65536))+") This long BRD packet will be received" # Broadcast a large packet so many hops are generated~
print('[Sending]', payload)
lora.send(dst_id=0, msg=payload, pkt_type=lora.PKT_TYPE['BRD']) # A broadcast request. Do not expect respond.

time.sleep(10)
payload = str(random.randint(100,65536))+") This long BRD packet will also be received even though a wrong dst_id is specified. It is BRD, dst_id does not matter~"
print('[Sending]', payload)
lora.send(dst_id=3, msg=payload, pkt_type=lora.PKT_TYPE['BRD']) # A broadcast request. Do not expect respond.
