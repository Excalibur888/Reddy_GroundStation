import os, sys, struct
import asyncio
import websockets
from LoRaRF import SX126x, LoRaSpi, LoRaGpio

currentdir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.dirname(os.path.dirname(currentdir)))

def uint8_to_int(uint1, uint2, uint3, uint4):
    result = (uint1 << 24) | (uint2 << 16) | (uint3 << 8) | uint4
    return result

def uint8_to_float(uint1, uint2, uint3, uint4):
    byte_string = struct.pack('BBBB', uint4, uint3, uint2, uint1)
    float_value = struct.unpack('f', byte_string)[0]
    return float_value

async def send_data_to_server(data):
    uri = "ws://localhost:80"  # WebSocket server URI
    async with websockets.connect(uri) as websocket:
        await websocket.send(data)


# Begin LoRa radio with connected SPI bus and IO pins (cs and reset) on GPIO
# SPI is defined by bus ID and cs ID and IO pins defined by chip and offset number
spi = LoRaSpi(0, 0)
cs = LoRaGpio(0, 8)
reset = LoRaGpio(0, 22)
busy = LoRaGpio(0, 23)
irq = LoRaGpio(0, 24)
txen = LoRaGpio(0, 12)
rxen = LoRaGpio(0, 6)

LoRa = SX126x(spi, cs, reset, busy, irq, txen, rxen)

print("Begin LoRa radio")
if not LoRa.begin() :
    raise Exception("Something wrong, can't begin LoRa radio")

# Configure LoRa to use TCXO with DIO3 as control
print("Set RF module to use TCXO as clock reference")
LoRa.setDio3TcxoCtrl(LoRa.DIO3_OUTPUT_1_8, LoRa.TCXO_DELAY_10)

# Set frequency to 915 Mhz
print("Set frequency to 915 Mhz")
LoRa.setFrequency(915000000)

# Set RX gain to power saving gain
print("Set RX gain to power saving gain")
LoRa.setRxGain(LoRa.RX_GAIN_BOOSTED)

# Configure modulation parameter including spreading factor (SF), bandwidth (BW), and coding rate (CR)
print("Set modulation parameters:\n\tSpreading factor = 7\n\tBandwidth = 125 kHz\n\tCoding rate = 4/5")
sf = 7
bw = 125000
cr = 5
ldro = False
LoRa.setLoRaModulation(sf, bw, cr, ldro)

# Configure packet parameter including header type, preamble length, payload length, and CRC type
print("Set packet parameters:\n\tExplicit header type\n\tPreamble length = 12\n\tPayload Length = 15\n\tCRC on")
headerType = LoRa.HEADER_EXPLICIT
preambleLength = 0x10
payloadLength = 0x2C
crcType = False
invertIq = False
LoRa.setLoRaPacket(headerType, preambleLength, payloadLength, crcType, invertIq)

# Set syncronize word for public network (0x3444)
print("Set syncronize word to 0x8888")
LoRa.setSyncWord(0x8888)

print("\n-- LoRa Receiver Continuous --\n")

# Request for receiving new LoRa packet in RX continuous mode
LoRa.request(LoRa.RX_CONTINUOUS)

# Receive message continuously
async def receive_and_send_data():
    while True :

        # Check for incoming LoRa packet
        if LoRa.available() :

            # Put received packet to message and counter variable
            message = ""
            while LoRa.available() > 0 :
                message += str(LoRa.read()) + " "

            # Print received message and counter in serial
            print(f"{message}")

            # Print packet/signal status including RSSI, SNR, and signalRSSI
            print("Packet status: RSSI = {0:0.2f} dBm | SNR = {1:0.2f} dB".format(LoRa.packetRssi(), LoRa.snr()))
            print("")

            # Show received status in case CRC or header error occur
            status = LoRa.status()
            if status == LoRa.STATUS_CRC_ERR : print("CRC error")
            if status == LoRa.STATUS_HEADER_ERR : print("Packet header error")

            sm = message.split(" ")
            sm.pop()

            if len(sm) != 44 : continue
            counter = uint8_to_int(int(sm[0]), int(sm[1]), int(sm[2]), int(sm[3]))
            accx = uint8_to_float(int(sm[4]), int(sm[5]), int(sm[6]), int(sm[7]))
            accy = uint8_to_float(int(sm[8]), int(sm[9]), int(sm[10]), int(sm[11]))
            accz = uint8_to_float(int(sm[12]), int(sm[13]), int(sm[14]), int(sm[15]))
            gyrox = uint8_to_float(int(sm[16]), int(sm[17]), int(sm[18]), int(sm[19]))
            gyroy = uint8_to_float(int(sm[20]), int(sm[21]), int(sm[22]), int(sm[23]))
            gyroz = uint8_to_float(int(sm[24]), int(sm[25]), int(sm[26]), int(sm[27]))
            magnetox = uint8_to_float(int(sm[28]), int(sm[29]), int(sm[30]), int(sm[31]))
            magnetoy = uint8_to_float(int(sm[32]), int(sm[33]), int(sm[34]), int(sm[35]))
            magnetoz = uint8_to_float(int(sm[36]), int(sm[37]), int(sm[38]), int(sm[39]))
            baro = uint8_to_float(int(sm[40]), int(sm[41]), int(sm[42]), int(sm[43]))

            # Prepare sensor data to send
            sensor_data = f"Counter: {counter}, AccX: {accx}, AccY: {accy}, AccZ: {accz}, GyroX: {gyrox}, GyroY: {gyroy}, GyroZ: {gyroz}, MagnetX: {magnetox}, MagnetY: {magnetoy}, MagnetZ: {magnetoz}, Baro: {baro}"

            # Print sensor data
            print("Sending sensor data:", sensor_data)

            # Send sensor data to server via WebSocket
            await send_data_to_server(sensor_data)

asyncio.run(receive_and_send_data())