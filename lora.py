import time, urandom, struct
from machine import Pin, SPI

class SX1276:
    def __init__(self, RST_Pin, CS_Pin, SPI_CH, SCK_Pin, MOSI_Pin, MISO_Pin, DIO0_Pin, DIO1_Pin, SRC_Id, FHSS_list, plus20dBm=False, debug=False):
        self.src_id       = SRC_Id  # id of packet sender
        self.pkt_id       = 0       # pkt_id is a random packet id. Why we need this ? If we ask the receiver return an acknowledgement, how do we know which packet it is acknowledging?
        self.pkt_type     = 0
        # REQ or Request    : Sender needs an ACK packet from the receiver as the response to this REQ packet
        # ACK or Acknowledge: Receiver sends this ACK response
        # BRD or Broadcast  : Sender needs no ACK response
        self.PKT_TYPE     = {'REQ':0, 'ACK':1, 'BRD':2}
        self.header_fmt   = 'HHHH' # src_id, dst_id, pkt_id, pkt_type
        self.header_size  = struct.calcsize(self.header_fmt)
        self._mode        = None
        self.FHSS_list    = FHSS_list
        self.debug        = debug
        self.is_available = False  # let the main code know Tx and RxCont is done
        ########################
        #                      #
        #  1. Reset the modem  #
        #                      #
        ########################
        rst_pin = Pin(RST_Pin, Pin.OUT)
        rst_pin.off()
        time.sleep(0.01)
        rst_pin.on()
        time.sleep(0.01)

        #################################
        #                               #
        #  2. SPI comm with the modem.  #
        #                               #
        #################################

        # Tx: Modem's wireless transmittion, Rx: Reception
        # Modem communicates with other modem since we command the modem to perform Tx/Rx operations via the SPI interface.
        # We disable SPI communication with the modem first, to ensure Tx/Rx operations only happends when we need.
        self.cs_pin = Pin(CS_Pin, Pin.OUT)
        self.cs_pin.on()                       # Release board from SPI Bus by bringing it into high impedance status.

        # SPI communication
        # See datasheet: Device support SPI mode 0 (polarity & phase = 0) up to a max of 10MHz.
        self.spi = SPI(SPI_CH, baudrate=10_000_000, polarity=0, phase=0,
                       sck=Pin(SCK_Pin), mosi=Pin(MOSI_Pin), miso=Pin(MISO_Pin)
                      )

        ####################
        #                  #
        #      3.Lora      #
        #                  #
        ####################
        self.RegTable = {  # register table
            'RegFifo'              : 0x00 ,
            'RegOpMode'            : 0x01 , # operation mode
            'RegFrfMsb'            : 0x06 ,
            'RegFrfMid'            : 0x07 ,
            'RegFrfLsb'            : 0x08 ,
            'RegPaConfig'          : 0x09 ,
            'RegFifoTxBaseAddr'    : 0x0e ,
            'RegFifoRxBaseAddr'    : 0x0f ,
            'RegFifoAddrPtr'       : 0x0d ,
            'RegFifoRxCurrentAddr' : 0x10 ,
            'RegIrqFlags'          : 0x12 ,
            'RegRxNbBytes'         : 0x13 , # Number of received bytes
            'RegPktSnrValue'       : 0x19 ,
            'RegPktRssiValue'      : 0x1a ,
            'RegRssiValue'         : 0x1b ,
            'RegHopChannel'        : 0x1c ,
            'RegModemConfig1'      : 0x1d ,
            'RegModemConfig2'      : 0x1e ,
            'RegPreambleMsb'       : 0x20 ,
            'RegPreambleLsb'       : 0x21 ,
            'RegPayloadLength'     : 0x22 ,
            'RegHopPeriod'         : 0x24 ,
            'RegModemConfig3'      : 0x26 ,
            'RegDioMapping1'       : 0x40 ,
            'RegVersion'           : 0x42 ,
            'RegPaDac'             : 0x4d
        }

        self.Mode = { # see Table 16 LoRa ® Operating Mode Functionality
            'SLEEP'        : 0b000,
            'STANDBY'      : 0b001,
            'TX'           : 0b011,
            'RXCONTINUOUS' : 0b101,
            'RXSINGLE'     : 0b110,
            'CAD'          : 0b111,
        }

        if True: # code folding
            # Choose LoRa mode and Test write/read functions
            LongRangeMode = 0b1
            # Choose LoRa (instead of FSK) mode for SX1276 and put the module in sleep mode
            self.spi_write('RegOpMode', self.Mode['SLEEP'] | LongRangeMode << 7)
            # Test read function
            assert self.spi_read('RegOpMode') == (self.Mode['SLEEP'] | LongRangeMode << 7), "LoRa initialization failed"

            # Set modem config: bandwidth, coding rate, header mode, spreading factor, CRC, and etc.
            # See 4.4. LoRa Mode Register Map
            Bw                   = {'125KHz':0b0111, '500kHz':0b1001}
            CodingRate           = {5:0b001, 6:0b010, 7:0b011, 8:0b100}
            ImplicitHeaderModeOn = {'Implicit':0b1, 'Explicit':0b0}
            self.spi_write('RegModemConfig1', Bw['125KHz'] << 4 | CodingRate[5] << 1 | ImplicitHeaderModeOn['Explicit'])

            SpreadingFactor  = {7:0x7, 9:0x9, 10:0xA, 12:0xC}
            TxContinuousMode = {'normal':0b0, 'continuous':0b1}
            RxPayloadCrcOn   = {'disable':0b0, 'enable':0b1}
            self.spi_write('RegModemConfig2', SpreadingFactor[10] << 4 | TxContinuousMode['normal'] << 3 | RxPayloadCrcOn['enable'] << 2 | 0x00) # Last 0x00 is SymbTimeout(9:8)

            LowDataRateOptimize = {'Disabled':0b0, 'Enabled':0b1}
            AgcAutoOn = {'register LnaGain':0b0, 'internal AGC loop':0b1}
            self.spi_write('RegModemConfig3', LowDataRateOptimize['Enabled'] << 3 | AgcAutoOn['internal AGC loop'] << 2)

            # Preamble length
            self.spi_write('RegPreambleMsb', 0x0) # Preamble can be (2^15)kb long, much longer than payload
            self.spi_write('RegPreambleLsb', 0x8) # but we just use 8-byte preamble

            # FHSS
            # How does SX1276 chip hop the freq spectrum?
            # First, two SX1276 chips were given a same series of frequencies (FHSS_list) in advance.
            # One SX1276 is configured as sender and another is receiver.
            # The sender is configured to be interrupted (IRQ) by 'TxDone' and 'FhssChangeChannel'
            # The receiver is configured to be interrupted by 'RxDone' and 'FhssChangeChannel'
            # After the chip spent enough (dwell) time on one frequency channel during Tx or Rx, 'FhssChangeChannel' IRQ is triggered.
            # New freq (next unused element in FHSS_list) is set in the 'FhssChangeChannel' IRQ handler.
            # After enough channels are hopped, Tx/Rx is done and TxDone/RxDone is triggered.

            # Symbol duration: Tsym = 2^SF / BW
            # For example, if SF = 10, BW = 125kHz, then Tsym = 8.192ms
            # Given FCC permits a 400ms max dwell time per channel, we must hop at least every 48 symbols
            # HoppingPeriod (dwell time on each freq) = FreqHoppingPeriod * Tsym
            # In the following code, the chip would hop freq for every 20 symbols.
            FreqHoppingPeriod = 20 # Symbol periods between freq hops.
            self.spi_write('RegHopPeriod', FreqHoppingPeriod) # HoppingPeriod = 20 * 8.192ms
            FhssPresentChannel = self.spi_read('RegHopChannel')

            # See 4.1.4. Frequency Settings
            FXOSC = 32e6 # Freq of XOSC
            self.FSTEP = FXOSC / (2**19)

            # Output Power
            # If desired output power is within -4 ~ +15dBm, use PA_LF or PA_HF as amplifier.
            # Use PA_BOOST as amplifier to output +2 ~ +17dBm continuous power or up to 20dBm peak power in a duty cycled operation.
            # Here we will always use PA_BOOST.
            # Since we use PA_BOOST, Pout = 2 + OutputPower and MaxPower could be any number (Why not 0b111/0x7?)
            PaSelect    = {'PA_BOOST':0b1, 'RFO':0b0} # Choose PA_BOOST (instead of RFO) as the power amplifier
            MaxPower    = {'15dBm':0x7, '13dBm':0x2}  # Pmax = 10.8 + 0.6 * 7
            OutputPower = {'17dBm':0xf, '2dBm':0x0}
            self.spi_write('RegPaConfig', PaSelect['PA_BOOST'] << 7 | MaxPower['15dBm'] << 4 | OutputPower['2dBm'])

            # Enables the +20dBm option on PA_BOOST pin.
            if plus20dBm: # PA (Power Amplifier) DAC (Digital Analog Converter)
                PaDac = {'default':0x04, 'enable_PA_BOOST':0x07} # Can be 0x04 or 0x07. 0x07 will enables the +20dBm option on PA_BOOST pin
                self.spi_write('RegPaDac', PaDac['enable_PA_BOOST'])

            # FIFO data buffer
            # SX1276 has a 256 byte memory area as the FIFO buffer for Tx/Rx operations.
            # How do we know which area is for Tx and which is for Rx.
            # We must set the base addresses RegFifoTxBaseAddr and RegFifoRxBaseAddr independently.
            # Since SX1276 work in a half-duplex manner, we better set both base addresses
            # at the bottom (0x00) of the FIFO buffer so that we can buffer 256 byte data
            # during transmition or reception.
            self.Fifo_Bottom = 0x00 # We choose this value to max buffer we can write (then send out)
            self.spi_write('RegFifoTxBaseAddr', self.Fifo_Bottom)
            self.spi_write('RegFifoRxBaseAddr', self.Fifo_Bottom)

        #######################
        #                     #
        #     4. Interrupt    #
        #                     #
        #######################

        # If configured, An TxDone IRQ is triggered transmittion finishes.
        # How to understand Table 18? When we want to set IRQ trigger, We use Table 18.
        # If we want RxDone triggers DIO0, we write 0b00 << 6 to RegDioMapping1. How we know it is 6? Because 6th and 7th bits are for DIO0.
        # Why 0b00 instead of 0b01? Because TxDone would trigger DIO0.
        # If we want FhssChangeChannel trigger DIO1, we write 0b01 << 4 to RegDioMapping1.
        # Why 0b01? See Table 18, col "DIO1", row "01"
        self.DioMapping = {
            'Dio0' : {
                         'RxDone'           : 0b00 << 6,
                         'TxDone'           : 0b01 << 6,
                         'CadDone'          : 0b10 << 6
                     },
            'Dio1' : {
                         'RxTimeout'        : 0b00 << 4,
                         'FhssChangeChannel': 0b01 << 4,
                         'CadDetected'      : 0b10 << 4
                     },
            'Dio2' : {
                         'FhssChangeChannel': 0b00 << 2,
                         'FhssChangeChannel': 0b01 << 2,
                         'FhssChangeChannel': 0b10 << 2
                     },
            'Dio3' : {   },
            'Dio4' : {   },
            'Dio5' : {
                         'ModeReady'        : 0b00 << 4,
                     },
        }

        self.DioMapping = {
            'Tx' : self.DioMapping['Dio0']['TxDone'] | self.DioMapping['Dio1']['FhssChangeChannel'],
            'Rx' : self.DioMapping['Dio0']['RxDone'] | self.DioMapping['Dio1']['FhssChangeChannel']
        }

        self.IrqFlags = {
            'RxTimeout'        : 0b1 << 7,
            'RxDone'           : 0b1 << 6,
            'PayloadCrcError'  : 0b1 << 5,
            'ValidHeader'      : 0b1 << 4,
            'TxDone'           : 0b1 << 3,
            'CadDone'          : 0b1 << 2,
            'FhssChangeChannel': 0b1 << 1,
            'CadDetected'      : 0b1 << 0,
        }

        dio0_pin = Pin(DIO0_Pin, Pin.IN)
        dio0_pin.irq(handler=self._irq_handler, trigger=Pin.IRQ_RISING)
        dio1_pin = Pin(DIO1_Pin, Pin.IN)
        dio1_pin.irq(handler=self._irq_handler, trigger=Pin.IRQ_RISING)
        self.mode = 'STANDBY' # Request Standby mode so SX1276 performs reception initialization.

    def spi_write(self, reg, data, fifo=False):
        wb = bytes([self.RegTable[reg] | 0x80]) # Create a writing byte
        if fifo:
            data = wb + data
        else:
            data = wb + bytes([data])
        self.cs_pin.value(0) # Bring the CS pin low to enable communication
        self.spi.write(data)
        self.cs_pin.value(1) # release the bus.

    def spi_read(self, reg=None, length=None):
        self.cs_pin.value(0)
        # https://docs.micropython.org/en/latest/library/machine.SPI.html#machine-softspi
        if length is None:
            data = self.spi.read(2, self.RegTable[reg])[1]
        else:
            data = self.spi.read(length+1, self.RegTable[reg])[1:]
        self.cs_pin.value(1)
        return data

    def set_freq(self):
        FhssPresentChannel = self.spi_read('RegHopChannel') & 0b00_111_111
        Frf = int(self.FHSS_list[FhssPresentChannel] / self.FSTEP)
        #if self.debug: print('[New CH]', FhssPresentChannel)
        self.spi_write('RegFrfMsb', (Frf >> 16) & 0xff)
        self.spi_write('RegFrfMid', (Frf >>  8) & 0xff)
        self.spi_write('RegFrfLsb',  Frf        & 0xff)

    @property
    def mode(self):
        return self._mode

    @mode.setter
    def mode(self, value):
        #print('[New mode]', value)
        if   value == 'TX':
            self.set_freq()
            self.spi_write('RegDioMapping1', self.DioMapping['Tx'])
            self.is_available = False
        elif value == 'RXCONTINUOUS':
            # Q: so why we use RXCONTINUOUS instead of RXSINGLE?
            # A: If you refers to page 39 of the datasheet, you will find RXSINGLE procedure has a Timeout mechanism.
            #    It is an energy-saving measure. The receiver wakes up from sleep mode and listen the channel.
            #    If it find nothing, it goes back to sleep.
            #    When we do regular commu, our receive will listen the channel indefinitely until we stop it actively.
            self.set_freq()
            self.spi_write('RegDioMapping1', self.DioMapping['Rx'])
            self.is_available = False
        elif value == 'STANDBY':
            self.spi_write('RegDioMapping1', 0x00)
        else:
            print('[Error] Unknown working mode')
        if self.mode != value:
            self.spi_write('RegOpMode', self.Mode[value])
            self._mode = value

    def read_fifo(self):
        self.spi_write('RegFifoAddrPtr', self.spi_read('RegFifoRxCurrentAddr'))
        packet     = self.spi_read('RegFifo', self.spi_read('RegRxNbBytes'))
        PacketSnr  = self.spi_read('RegPktSnrValue')
        SNR        = struct.unpack_from('b', bytes([PacketSnr]))[0] / 4
        PacketRssi = self.spi_read('RegPktRssiValue')
        #Rssi = read(RegRssiValue)
        if SNR < 0:
            RSSI = -157 + PacketRssi + SNR
        else:
            RSSI = -157 + 16 / 15 * PacketRssi
        RSSI = round(RSSI, 2) # Table 7 Frequency Synthesizer Specification
        return packet, SNR, RSSI

    def write_fifo(self, data):
        self.spi_write('RegFifoAddrPtr', self.Fifo_Bottom)
        self.spi_write('RegFifo', data, fifo=True)            # Write Data FIFO
        self.spi_write('RegPayloadLength', len(data))

    def send(self, dst_id=0, pkt_id=0, pkt_type=0, msg='', retry=1, timeout=9, debug=False): # src_id, dst_id,
        if len(msg)  > 240: raise                               # cannot send a too large message
        # 1. Create header
        # 2. Put header and message together
        # 3. Write payload to FIFO
        # 4. Put the modem in Tx mode so payload is sent out
        # 5. Then put the modem in Rx mode and wait 15 seconds if the packet is asking receiver to acknowledge.
        # 6. Or wait no time if the packet is for broadcasting or is for acknowledging
        # [Tx side] self.pkt_type = req ; Mode = Tx ; TxDone; RxCont
        # [Rx side] RxDone ; Mode = STANDBY ; send 'ACK'
        self.pkt_type = pkt_type
        if pkt_type == self.PKT_TYPE['REQ']:
            pkt_id      = urandom.randint(1,65535)
            self.pkt_id = pkt_id
        header = struct.pack(self.header_fmt, self.src_id, dst_id, pkt_id, pkt_type)
        data = header + msg.encode() 

        if pkt_type == self.PKT_TYPE['REQ']: 
            for _ in range(retry):
                self.mode = 'STANDBY'
                self.write_fifo(data)
                self.mode = 'TX'               # Request Standby mode so SX1276 send out payload
                for _ in range(timeout):
                    if self.pkt_id == 0:
                        break
                    time.sleep(1)
                else:
                    if debug: print('[Debug] REQ is not ACKed before timeout is triggered') # No break means no response in 5 seconds
                if self.pkt_id == 0:
                    break
            else:
                if debug: print('[Debug] Resend the REQ packet {} times but it is still not ACKed'.format(retry)) # No break means no response in 5 seconds
        elif pkt_type in [self.PKT_TYPE['ACK'], self.PKT_TYPE['BRD']]: 
            self.mode = 'STANDBY'
            self.write_fifo(data)
            self.mode = 'TX'                            
        else:
            print("Unsupported Packet Type") 

    def _irq_handler(self, pin):
        irq_flags = self.spi_read('RegIrqFlags')
        self.spi_write('RegIrqFlags', 0xff)                   # write 0xff could clear all types of interrupt pkt_type 
        # For one complete "Request for acknowledgement" communication, there are 4 critical points (CP):
        # Step 0: The receiver is put in RxCont mode.
        # Step 1: The sender Tx something then IRQ TxDone is trigger on the sender. (1st critical point)
        # Step 2: In the irq handler of the sender, "mode shifts from Tx to RxCont" so the sender prepares to listen the ACK response (step 8).
        # Step 3: An IRQ RxDone is trigger on all receivers. (2nd CP)
        # Step 4: In the irq handler, if dst_id matches self.src_id, the receiver know it is the right recipient.
        # Step 5: The right receiver will shift mode to STANDBY before Tx the ACK.
        # Step 6: The receiver Tx the ACK then IRQ TxDone is trigger on the RECEIVER. (3rd CP)
        # Step 7: In the irq handler, the receiver will be put in STANDBY mode for further use.
        # Step 8: The sender catch the ACK response (see step 2) when IRQ RxDone is triggered on the sender. (4th CP)
        # Step 9: In the irq handler, the sender's mode is shifted from RxCont to STANDBY for further use. Done
        if irq_flags & self.IrqFlags['TxDone']:
            # When Tx mode is requested and data is send out, TxDone is triggered.
            if   self.pkt_type == self.PKT_TYPE['REQ']:
                # Sender's REQ Tx will meet this condition
                # 1st critical point (CP), mode shifts from Tx to RxCont
                self.mode = 'RXCONTINUOUS'
            elif self.pkt_type == self.PKT_TYPE['ACK']:
                # 3rd CP: Receiver's ACK response will meet this condition
                # Since we are doing two-way communication, now the receiver should be freed.
                #self.mode = 'STANDBY'
                self.is_available = True # Free the receiver
            elif self.pkt_type == self.PKT_TYPE['BRD']:
                self.is_available = True # Free the sender after broadcasting
            self.after_TxDone(None)

        elif irq_flags & self.IrqFlags['RxDone']:
            packet, SNR, RSSI = self.read_fifo() # read fifo
            if irq_flags & self.IrqFlags['PayloadCrcError']:
                print('[PayloadCrcError]', packet)
            else:
                if len(packet) < self.header_size:
                    print(packet, SNR, RSSI)
                    return
                header, data = packet[:self.header_size], packet[self.header_size:] # extract header
                src_id, dst_id, pkt_id, pkt_type = struct.unpack(self.header_fmt, header) # parse header
                if self.debug: print('[Debug] Rx',pkt_type)
                if   pkt_type == self.PKT_TYPE['REQ']:     # REQ Received
                    # Receiver will get a REQ packet from the sender and meet this condition
                    if dst_id == self.src_id:
                        # 2nd CP
                        self.mode = 'STANDBY'
                        self.send(dst_id=src_id, pkt_id=pkt_id, pkt_type=self.PKT_TYPE['ACK'], msg='') # This is an ack message
                        #print("We received a REQ packet and its dst_id matches our src_id. We are going to acknowledge it.")
                        self.req_packet_handler(None, data, SNR, RSSI)
                        if self.debug: print("[RxDone] Right REQ receiver")
                    else:
                        #self.req_packet_handler(None, data, SNR, RSSI)
                        # Shifting from 'RXCONTINUOUS' to 'RXCONTINUOUS' is not needed but we need reset IRQ
                        self.mode = 'RXCONTINUOUS'
                        if self.debug: print("[RxDone] Wrong REQ receiver") # We received a REQ packet but its dst_id does not match our src_id.
                        # We are not going to acknowledge it but we still display its content.
                elif pkt_type == self.PKT_TYPE['ACK']:     # ACK Received
                    if pkt_id == self.pkt_id:
                        # 4th CP: The right sender get an ACK packet from the receiver and meet this condition
                        self.pkt_id = 0                    # clear pkt_id so waiting in send function ends
                        self.mode = 'STANDBY'              # The sender has got the ACK packet so we shift way from RxCont mode.
                        self.is_available = True           # Free the sender
                        if self.debug: print("[RxDone] Right ACK receiver") # REQ is ACKed
                    else:
                        #print("We are not the original sender although we have received an ACK response. Ignore it.")
                        self.mode = 'RXCONTINUOUS'
                        if self.debug: print("[RxDone] Wrong ACK receiver") 
                elif pkt_type == self.PKT_TYPE['BRD']:
                    # BRD Received by the receiver. Do nothing.
                    self.brd_packet_handler(None, data, SNR, RSSI)
                    #print("We received a BRD packet whose sender does not expect an acknowledgement.")
                    self.mode = 'RXCONTINUOUS'
                    if self.debug: print("[RxDone] BRD receiver")
                else:
                    print('[Error]', packet, SNR, RSSI)

        elif irq_flags & self.IrqFlags['FhssChangeChannel']:
            self.set_freq()
        else:
            for i, j in self.IrqFlags.items():
                if irq_flags & j:
                    print('[Sth went wrong]', i)

    def req_packet_handler(self, data, SNR, RSSI):
        pass

    def brd_packet_handler(self, data, SNR, RSSI):
        pass

    def after_TxDone(self, _):
        pass
