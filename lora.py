import time, urandom, struct
from machine import Pin, SPI

class SX1276:
    def __init__(self, RST_Pin, CS_Pin, SPI_CH, SCK_Pin, MOSI_Pin, MISO_Pin, DIO0_Pin, DIO1_Pin, SRC_Id, FHSS_list, plus20dBm=False):
        self.src_id      = SRC_Id
        self.seq_num     = 0
        self.flags       = 0
        self.FLAG        = {'REQ':0, 'ACK':1, 'BRD':2} # Request: need ack response, Acknowledge: ack response, Broadcast: no need for response
        self.header_fmt  = 'HHHH' # src_id, dst_id, seq_num, flag (req / ack)
        self.header_size = struct.calcsize(self.header_fmt)
        self._mode       = None
        self.FHSS_list   = FHSS_list
        self.test_flag   = None # Test if ack is received~
        ####################
        #                  #
        #     1.Reset      #
        #                  #
        ####################
        # Reset LoRa Module
        rst_pin = Pin(RST_Pin, Pin.OUT)
        rst_pin.off()
        time.sleep(0.01)
        rst_pin.on()
        time.sleep(0.01)

        ####################
        #                  #
        #      2.SPI       #
        #                  #
        ####################
        '''
        Tx: Transmittion, Rx: Reception
        We command LoRa module to perform Tx/Rx operations via the SPI interface.
        We disable SPI communication first to ensure it only happends when we need.
        Define communication functions read and write.
        The SPI comm is enabled temporarily for reading and writing and disabled thereafter.
        '''
        # Disable SPI communication with the LoRa module
        self.cs_pin = Pin(CS_Pin, Pin.OUT)
        self.cs_pin.on() # Release board from SPI Bus by bringing it into high impedance status.

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
            '''
            How does SX1276 chip hop: Two SX1276 chips were given a same series of frequencies, they can do freq hopping across the series. 
            An IRQ was triggered after the chip spent enough (dwell) time in one frequency then the freq was reset in the handler.
            Symbol duration: Tsym = 2^SF / BW
            For example, if SF = 10, BW = 125kHz, then Tsym = 8.192ms
            Given FCC permits a 400ms max dwell time per channel, we must hop at least every 48 symbols
            HoppingPeriod (dwell time on each freq) = FreqHoppingPeriod * Tsym 
            In the following code, the chip would hop for every 20 symbols.
            '''
            FreqHoppingPeriod = 20 # Symbol periods between freq hops. 
            self.spi_write('RegHopPeriod', FreqHoppingPeriod) # HoppingPeriod = 20 * 8.192ms
            FhssPresentChannel = self.spi_read('RegHopChannel')

            # See 4.1.4. Frequency Settings
            FXOSC = 32e6 # Freq of XOSC
            self.FSTEP = FXOSC / (2**19) 
            Frf = int(self.FHSS_list[FhssPresentChannel] / self.FSTEP) 
            self.spi_write('RegFrfMsb', (Frf >> 16) & 0xff)
            self.spi_write('RegFrfMid', (Frf >>  8) & 0xff)
            self.spi_write('RegFrfLsb',  Frf        & 0xff)

            # Output Power
            '''
            If desired output power is within -4 ~ +15dBm, use PA_LF or PA_HF as amplifier.
            Use PA_BOOST as amplifier to output +2 ~ +17dBm continuous power or up to 20dBm
              peak power in a duty cycled operation.
            Here we will always use PA_BOOST.
            Since we use PA_BOOST, Pout = 2 + OutputPower and MaxPower could be any number (Why not 0b111/0x7?)
            '''
            PaSelect    = {'PA_BOOST':0b1, 'RFO':0b0} # Choose PA_BOOST (instead of RFO) as the power amplifier
            MaxPower    = {'15dBm':0x7, '13dBm':0x2}  # Pmax = 10.8 + 0.6 * 7
            OutputPower = {'17dBm':0xf, '2dBm':0x0}
            self.spi_write('RegPaConfig', PaSelect['PA_BOOST'] << 7 | MaxPower['15dBm'] << 4 | OutputPower['2dBm'])

            # Enables the +20dBm option on PA_BOOST pin.
            if plus20dBm: # PA (Power Amplifier) DAC (Digital Analog Converter)
                PaDac = {'default':0x04, 'enable_PA_BOOST':0x07} # Can be 0x04 or 0x07. 0x07 will enables the +20dBm option on PA_BOOST pin
                self.spi_write('RegPaDac', PaDac['enable_PA_BOOST'])

            # FIFO data buffer
            '''
            SX1276 has a 256 byte memory area as the FIFO buffer for Tx/Rx operations.
            How do we know which area is for Tx and which is for Rx.
            We must set the base addresses RegFifoTxBaseAddr and RegFifoRxBaseAddr independently.
            Since SX1276 work in a half-duplex manner, we better set both base addresses
            at the bottom (0x00) of the FIFO buffer so that we can buffer 256 byte data
            during transmition or reception.
            '''
            self.Fifo_Bottom = 0x00 # We choose this value to max buffer we can write (then send out)
            self.spi_write('RegFifoTxBaseAddr', self.Fifo_Bottom)
            self.spi_write('RegFifoRxBaseAddr', self.Fifo_Bottom)


        ####################
        #                  #
        #    4.Interrupt   #
        #                  #
        ####################
        '''
        # This section is optional for Tx.
        # It enable an interrupt when Tx is done.
        # How to understand Table 18? When we want to set IRQ trigger, We use Table 18.
        # If we want RxDone triggers DIO0, we write 0b00 << 6 to RegDioMapping1. How we know it is 6? Because 6th and 7th bits are for DIO0. 
        # Why 0b00 instead of 0b01? Because TxDone would trigger DIO0.  
        '''
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

    @property
    def mode(self):
        return self._mode

    @mode.setter
    def mode(self, value):
        if self.mode != value:
            if   value == 'TX':
                self.spi_write('RegDioMapping1', self.DioMapping['Dio0']['TxDone'] | self.DioMapping['Dio1']['FhssChangeChannel'])
            elif value == 'RXCONTINUOUS':
                self.spi_write('RegDioMapping1', self.DioMapping['Dio0']['RxDone'] | self.DioMapping['Dio1']['FhssChangeChannel'])
            elif value == 'STANDBY':
                self.spi_write('RegDioMapping1', 0x00)
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

    def send(self, dst_id=0, seq_num=0, flags=0, msg=''):     # src_id, dst_id,
        '''
        Create header
        Put header and message together
        Write payload to FIFO
        Request Tx mode so payload is sent out
        wait 15 seconds for ack request (ask receiver to acknowledge)
        wait no time for ack Tx (acknowledge transmittion)
        '''
        if   flags == self.FLAG['ACK']:                             # if this is ack Tx, it generates no ack_token
            pass
        elif flags == self.FLAG['REQ']:
            if len(msg)  > 240: raise                               # cannot send a too large message
            seq_num      = urandom.randint(1,65535)
            self.seq_num = seq_num
        elif flags == self.FLAG['BRD']:
            if len(msg)  > 240: raise                               # cannot send a too large message
        header = struct.pack(self.header_fmt, self.src_id, dst_id, seq_num, flags)
        data = header + msg.encode()
        self.write_fifo(data)
        self.mode = 'TX'                                            # Request Standby mode so SX1276 send out payload
        if flags in [self.FLAG[i] for i in ['ACK','BRD']]:
            return # no wait for ack when send out ack or broadcast
        for _ in range(5):
            if self.seq_num:
                time.sleep(3)
            else: # ack_token is cleaned in Rx IRS so send succeeded.
                break
        else:
            print('Sending Timeout')

    def _irq_handler(self, pin):
        irq_flags = self.spi_read('RegIrqFlags')
        self.spi_write('RegIrqFlags', 0xff)                   # write 0xff could clear all types of interrupt flags

        if irq_flags & self.IrqFlags['TxDone']:    
            '''
            When Tx mode is requested and data is send out, TxDone is triggered.
            Then request Rx mode and wait for acknowledgement
            '''
            if   self.flags == self.FLAG['REQ']:
                self.mode = 'RXCONTINUOUS'
            elif self.flags == self.FLAG['ACK']:
                pass
            elif self.flags == self.FLAG['BRD']:
                pass
            self.after_TxDone(None)

        elif irq_flags & self.IrqFlags['RxDone']:    
            if irq_flags & self.IrqFlags['PayloadCrcError']:    
                packet, SNR, RSSI                   = self.read_fifo() # read fifo 
                print('PayloadCrcError:', packet)
            else:
                packet, SNR, RSSI                   = self.read_fifo() # read fifo
                if len(packet) < self.header_size:
                    print(packet, SNR, RSSI)
                    return
                header, data                        = packet[:self.header_size], packet[self.header_size:] # extract header
                src_id, dst_id, seq_num, flags = struct.unpack(self.header_fmt, header) # parse header
                if   flags == self.FLAG['REQ']:            # REQ Received
                    if dst_id == self.src_id:
                        pass
                    elif dst_id != self.src_id:            # Not the right receiver
                        return                             # Do not response
                    self.send(dst_id=src_id, seq_num=seq_num, flags=self.FLAG['ACK'], msg='') # Thi is a ack message
                    self.req_packet_handler(None, data, SNR, RSSI)
                elif flags == self.FLAG['ACK']:              # ACK Received
                    if seq_num == self.seq_num:            # Sender receives acknowledgement 
                        self.test_flag = True
                        self.mode    = 'STANDBY'
                        self.seq_num = 0                   # clear seq_num so waiting in send function ends
                    else:                                  # Wrong acknowledgement
                        self.test_flag = False
                        return                             # Ignore so Rx continues
                elif flags == self.FLAG['BRD']:            # BRD Received
                    self.brd_packet_handler(None, data, SNR, RSSI)
                else:
                    print(packet, SNR, RSSI)

        elif irq_flags & self.IrqFlags['FhssChangeChannel']:    
            '''
            '''
            FhssPresentChannel = self.spi_read('RegHopChannel') 
            Frf = int(self.FHSS_list[FhssPresentChannel] / self.FSTEP)
            self.spi_write('RegFrfMsb', (Frf >> 16) & 0xff)
            self.spi_write('RegFrfMid', (Frf >>  8) & 0xff)
            self.spi_write('RegFrfLsb',  Frf        & 0xff)
        else:
            for i, j in self.IrqFlags.items():
                if irq_flags & j:
                    print(i)

    def req_packet_handler(self, data, SNR, RSSI):
        pass

    def brd_packet_handler(self, data, SNR, RSSI):
        pass

    def after_TxDone(self):
        pass
