import os, sys
currentdir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.dirname(os.path.dirname(currentdir)))
from LoRaRF import SX126x, LoRaSpi, LoRaGpio
import time
from threading import Thread

spi = LoRaSpi(0, 0)
cs = LoRaGpio(0, 8)
reset = LoRaGpio(0, 22)
busy = LoRaGpio(0, 23)
irq = LoRaGpio(0, 5)
txen = LoRaGpio(0, 1)
rxen = LoRaGpio(0, 0)

LoRa = SX126x(spi, cs, reset, busy, irq)

dio3Voltage = LoRa.DIO3_OUTPUT_1_8
tcxoDelay = LoRa.TCXO_DELAY_10

rfFrequency = 915000000
gain = LoRa.RX_GAIN_BOOSTED

sf = 12
bw = LoRa.BW_125000
cr = LoRa.CR_4_6
ldro = LoRa.LDRO_OFF

preambleLength = 0x10
headerType = LoRa.HEADER_EXPLICIT
payloadLength = 0x02
crcType = LoRa.CRC_OFF
invertIq = LoRa.IQ_STANDARD

sw = [0x88, 0x88]

received = False

def checkReceiveDone() :
    global received
    received = True

def settingFunction() :

    print("-- SETTING FUNCTION --")

    # Reset RF module by setting resetPin to LOW and begin SPI communication
    print("Resetting RF module")
    LoRa.reset()
    LoRa.setStandby(LoRa.STANDBY_RC)
    if not LoRa.busyCheck() :
        print("Going to standby mode")
    else :
        print("Something wrong, can't set to standby mode")

    # Optionally configure TCXO or XTAL used in RF module
    print("Set RF module to use TCXO as clock reference")
    LoRa.setDio3AsTcxoCtrl(dio3Voltage, tcxoDelay)
    # print("Set RF module to use XTAL as clock reference")
    # LoRa.writeRegister(LoRa.REG_XTA_TRIM, xtalCap, 2)

    # Optionally configure DIO2 as RF switch control
    print("Set RF switch is controlled by DIO2")
    LoRa.setDio2AsRfSwitchCtrl(LoRa.DIO2_AS_RF_SWITCH)

    # Set packet type to LoRa
    print("Set packet type to LoRa")
    LoRa.setPacketType(LoRa.LORA_MODEM)

    # Set frequency to selected frequency (rfFrequency = rfFreq * 32000000 / 2 ^ 25)
    print(f"Set frequency to {rfFrequency/1000000} Mhz")
    rfFreq = int(rfFrequency * 33554432 / 32000000)
    print(f"SFQ={rfFreq}")
    LoRa.setRfFrequency(rfFreq)

    # Set rx gain to selected gain
    if gain == LoRa.RX_GAIN_BOOSTED : gainMsg = "boosted gain"
    else : gainMsg = "power saving gain"
    print(f"Set RX gain to {gainMsg} dBm")
    LoRa.writeRegister(LoRa.REG_RX_GAIN, [gain], 1)

    # Configure modulation parameter with predefined spreading factor, bandwidth, coding rate, and low data rate optimize setting
    print("Set modulation with predefined parameters")
    LoRa.setModulationParamsLoRa(sf, bw, cr, ldro)

    # Configure packet parameter with predefined preamble length, header mode type, payload length, crc type, and invert iq option
    print("Set packet with predefined parameters")
    LoRa.setPacketParamsLoRa(preambleLength, headerType, payloadLength, crcType, invertIq)

    # Set predefined syncronize word
    print("Set syncWord to 0x{0:02X}{1:02X}".format(sw[0], sw[1]))
    LoRa.writeRegister(LoRa.REG_LORA_SYNC_WORD_MSB, sw, 2)

def receiveFunction(message: list, timeout: int) -> int :

    print("\n-- RECEIVE FUNCTION --")

    # Activate interrupt when receive done on DIO1
    print("Set RX done, timeout, and CRC error IRQ on DIO1")
    mask = LoRa.IRQ_RX_DONE | LoRa.IRQ_TIMEOUT | LoRa.IRQ_CRC_ERR
    LoRa.setDioIrqParams(mask, mask, LoRa.IRQ_NONE, LoRa.IRQ_NONE)
    # Attach irqPin to DIO1
    print(f"Attach interrupt on IRQ pin")
    monitoring = Thread(target=irq.monitor, args=(checkReceiveDone, 0.1))
    monitoring.start()

    # Set rxen and txen pin state for receiving packet
    if txen != None and rxen != None :
        txen.output(LoRaGpio.LOW)
        rxen.output(LoRaGpio.HIGH)

    # Calculate timeout (timeout duration = timeout * 15.625 us)
    tOut = timeout * 64
    # Set RF module to RX mode to receive message
    print("Receiving LoRa packet within predefined timeout")
    LoRa.setRx(tOut)

    # Wait for RX done interrupt
    print("Wait for RX done interrupt")
    global received
    while not received :
#        print(f"Mode : {LoRa.getMode()>>4}")
#        print(f"Status : {LoRa.getStatus()&0x0E}")
#        print(f"IRQStatus : {LoRa.getIrqStatus()}")
#        print(f"Errors : {LoRa.getError()}")
#        print(f"PacketStatus : {LoRa._readBytes(0x14, 4)}")
#        print("")
#        payloadLengthRx = 0; rxStartBufferPointer = 0
#        (payloadLengthRx, rxStartBufferPointer) = LoRa.getRxBufferStatus()
#        buffer = LoRa.readBuffer(rxStartBufferPointer, payloadLengthRx)
#        for buf in buffer : message.append(buf)
#        print(f"Message in bytes : {buffer}")
#        messageString = ""
#        for i in range(len(message)) : messageString += chr(message[i])
#        print(f"Message: \'{messageString}\'")
        pass
    monitoring.join()
    # Clear transmit interrupt flag
    received = False

    # Clear the interrupt status
    irqStat = LoRa.getIrqStatus()
    print("Clear IRQ status")
    LoRa.clearIrqStatus(irqStat)
    if rxen != None :
        rxen.output(LoRaGpio.LOW)

    # Exit function if timeout reached
    if irqStat & LoRa.IRQ_TIMEOUT :
        return irqStat
    print("Packet received!")

    # Get last received length and buffer base address
    print("Get received length and buffer base address")
    payloadLengthRx = 0; rxStartBufferPointer = 0
    (payloadLengthRx, rxStartBufferPointer) = LoRa.getRxBufferStatus()

    # Get and display packet status
    print("Get received packet status")
    rssiPkt = 0; snrPkt = 0; signalRssiPkt = 0
    (rssiPkt, snrPkt, signalRssiPkt) = LoRa.getPacketStatus()
    rssi = rssiPkt / -2
    snr = snrPkt / 4
    signalRssi = signalRssiPkt / -2
    print(f"Packet status: RSSI = {rssi} | SNR = {snr} | signalRSSI = {signalRssi}")

    # Read message from buffer
    print("Read message from buffer")
    buffer = LoRa.readBuffer(rxStartBufferPointer, payloadLengthRx)
    for buf in buffer : message.append(buf)
    print(f"Message in bytes : {buffer}")

    # Return interrupt status
    return irqStat
LoRa.begin()
settingFunction()

while True :

    # Receive message
    message = []
    timeout = 1000                  # ms timeout (0 = continuous)
    print(f"Mode : {LoRa.getMode()>>4}")
    print(f"Status : {LoRa.getStatus()&0x0E}")
    print(f"IRQStatus : {LoRa.getIrqStatus()}")
    print(f"Errors : {LoRa.getError()}")

    status = receiveFunction(message, timeout)

    # Display message if receive success or display status if error
    if status & LoRa.IRQ_RX_DONE :
        messageString = ""
        for i in range(len(message)) : messageString += chr(message[i])
        print(f"Message: \'{messageString}\'")
    elif status & LoRa.IRQ_TIMEOUT :
        print("Receive timeout")
    elif status & LoRa.IRQ_CRC_ERR :
        print("CRC error")
