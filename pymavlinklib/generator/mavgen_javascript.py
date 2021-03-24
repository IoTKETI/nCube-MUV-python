#!/usr/bin/env python
'''
parse a MAVLink protocol XML file and generate a Node.js javascript module implementation

Based on original work Copyright Andrew Tridgell 2011
Released under GNU GPL version 3 or later
'''
from __future__ import print_function

from builtins import range

import os
import textwrap
from . import mavtemplate
import sys

t = mavtemplate.MAVTemplate()


def get_mavhead(xml):
    return ("mavlink20" if xml.protocol_marker == 253 else "mavlink10")

def get_mavprocessor(xml):
    return ("MAVLink20Processor" if xml.protocol_marker == 253 else "MAVLink10Processor")

def generate_preamble(outf, msgs, args, xml):
    print("Generating preamble")
    t.write(outf, """
/*
MAVLink protocol implementation for node.js (auto-generated by mavgen_javascript.py)

Generated from: ${FILELIST}

Note: this file has been auto-generated. DO NOT EDIT
*/

jspack = require("jspack").jspack,
    _ = require("underscore"),
    events = require("events"), // for .emit(..), MAVLink20Processor inherits from events.EventEmitter
    util = require("util");

var Long = require('long');

// Add a convenience method to Buffer
Buffer.prototype.toByteArray = function () {
  return Array.prototype.slice.call(this, 0)
}

${MAVHEAD} = function(){};

// Implement the X25CRC function (present in the Python version through the mavutil.py package)
${MAVHEAD}.x25Crc = function(buffer, crcIN) {

    var bytes = buffer;
    var crcOUT = crcIN || 0xffff;
    _.each(bytes, function(e) {
        var tmp = e ^ (crcOUT & 0xff);
        tmp = (tmp ^ (tmp << 4)) & 0xff;
        crcOUT = (crcOUT >> 8) ^ (tmp << 8) ^ (tmp << 3) ^ (tmp >> 4);
        crcOUT = crcOUT & 0xffff;
    });
    return crcOUT;

}

${MAVHEAD}.WIRE_PROTOCOL_VERSION = "${WIRE_PROTOCOL_VERSION}";
${MAVHEAD}.HEADER_LEN = ${HEADERLEN};

${MAVHEAD}.MAVLINK_TYPE_CHAR     = 0
${MAVHEAD}.MAVLINK_TYPE_UINT8_T  = 1
${MAVHEAD}.MAVLINK_TYPE_INT8_T   = 2
${MAVHEAD}.MAVLINK_TYPE_UINT16_T = 3
${MAVHEAD}.MAVLINK_TYPE_INT16_T  = 4
${MAVHEAD}.MAVLINK_TYPE_UINT32_T = 5
${MAVHEAD}.MAVLINK_TYPE_INT32_T  = 6
${MAVHEAD}.MAVLINK_TYPE_UINT64_T = 7
${MAVHEAD}.MAVLINK_TYPE_INT64_T  = 8
${MAVHEAD}.MAVLINK_TYPE_FLOAT    = 9
${MAVHEAD}.MAVLINK_TYPE_DOUBLE   = 10

${MAVHEAD}.MAVLINK_IFLAG_SIGNED = 0x01

// Mavlink headers incorporate sequence, source system (platform) and source component. 
${MAVHEAD}.header = function(msgId, mlen, seq, srcSystem, srcComponent, incompat_flags=0, compat_flags=0,) {

    this.mlen = ( typeof mlen === 'undefined' ) ? 0 : mlen;
    this.seq = ( typeof seq === 'undefined' ) ? 0 : seq;
    this.srcSystem = ( typeof srcSystem === 'undefined' ) ? 0 : srcSystem;
    this.srcComponent = ( typeof srcComponent === 'undefined' ) ? 0 : srcComponent;
    this.msgId = msgId
    this.incompat_flags = incompat_flags
    this.compat_flags = compat_flags

}
""", {'FILELIST' : ",".join(args),
      'PROTOCOL_MARKER' : xml.protocol_marker,
      'crc_extra' : xml.crc_extra,
      'WIRE_PROTOCOL_VERSION' : ("2.0" if xml.protocol_marker == 253 else "1.0"),
      'MAVHEAD': get_mavhead(xml),
      'HEADERLEN': ("10" if xml.protocol_marker == 253 else "6")})

    # Mavlink2
    if (xml.protocol_marker == 253):
        t.write(outf, """
${MAVHEAD}.header.prototype.pack = function() {
    return jspack.Pack('BBBBBBBHB', [${PROTOCOL_MARKER}, this.mlen, this.incompat_flags, this.compat_flags, this.seq, this.srcSystem, this.srcComponent, ((this.msgId & 0xFF) << 8) | ((this.msgId >> 8) & 0xFF), this.msgId>>16]);
}
        """, {'PROTOCOL_MARKER' : xml.protocol_marker,
              'MAVHEAD': get_mavhead(xml)})
    # Mavlink1
    else:
        t.write(outf, """

${MAVHEAD}.header.prototype.pack = function() {
    return jspack.Pack('BBBBBB', [${PROTOCOL_MARKER}, this.mlen, this.seq, this.srcSystem, this.srcComponent, this.msgId]);
}
        """, {'PROTOCOL_MARKER' : xml.protocol_marker,
              'MAVHEAD': get_mavhead(xml)})

    t.write(outf, """

// Base class declaration: mavlink.message will be the parent class for each
// concrete implementation in mavlink.messages.
${MAVHEAD}.message = function() {};

// Convenience setter to facilitate turning the unpacked array of data into member properties
${MAVHEAD}.message.prototype.set = function(args,verbose) {
// inspect
    _.each(this.fieldnames, function(e, i) {
        var num = parseInt(i,10);
        if (this.hasOwnProperty(e) && isNaN(num)  ){ // asking for an attribure thats non-numeric is ok unless its already an attribute we have
            console.log("WARNING, overwriting an existing property is DANGEROUS:"+e+" ==>"+i+"==>"+args[i]+" -> "+JSON.stringify(this)); 
        }
    }, this);
// then modify
    _.each(this.fieldnames, function(e, i) {
        this[e] = args[i];
    }, this);
};

// This pack function builds the header and produces a complete MAVLink message,
// including header and message CRC.
${MAVHEAD}.message.prototype.pack = function(mav, crc_extra, payload) {

    this._payload = payload;
    var plen = this._payload.length;
""", {'MAVHEAD': get_mavhead(xml)})

    # Mavlink2 only
    if (xml.protocol_marker == 253):
        t.write(outf, """
        //in MAVLink2 we can strip trailing zeros off payloads. This allows for simple
        // variable length arrays and smaller packets
        while (plen > 1 && this._payload[plen-1] == 0) {
                plen = plen - 1;
        }
        this._payload = this._payload.slice(0, plen);
    """)

    t.write(outf, """
    var incompat_flags = 0;
    this._header = new ${MAVHEAD}.header(this._id, this._payload.length, mav.seq, mav.srcSystem, mav.srcComponent, incompat_flags, 0,);    
    this._msgbuf = this._header.pack().concat(this._payload);
    var crc = ${MAVHEAD}.x25Crc(this._msgbuf.slice(1));

    // For now, assume always using crc_extra = True.  TODO: check/fix this.
    crc = ${MAVHEAD}.x25Crc([crc_extra], crc);
    this._msgbuf = this._msgbuf.concat(jspack.Pack('<H', [crc] ) );
    return this._msgbuf;

}

""", {'MAVHEAD': get_mavhead(xml)})

def generate_enums(outf, enums, xml):
    print("Generating enums")
    outf.write("\n// enums\n")
    wrapper = textwrap.TextWrapper(initial_indent="", subsequent_indent="                        // ")
    for e in enums:
        outf.write("\n// %s\n" % e.name)
        for entry in e.entry:
            t.write(outf, "${MAVHEAD}.${ENUMNAME} = ${ENUMVAL} // ${ENUMDESC}\n", {'ENUMNAME': entry.name,
                                                                                'ENUMVAL': entry.value,
                                                                                'ENUMDESC': wrapper.fill(entry.description),
                                                                                'MAVHEAD': get_mavhead(xml)})

def generate_message_ids(outf, msgs, xml):
    print("Generating message IDs")
    outf.write("\n// message IDs\n")
    t.write(outf, "${MAVHEAD}.MAVLINK_MSG_ID_BAD_DATA = -1\n", {'MAVHEAD': get_mavhead(xml)})
    for m in msgs:
        t.write(outf, "${MAVHEAD}.MAVLINK_MSG_ID_${MNAME} = ${MVAL}\n", {'MAVHEAD': get_mavhead(xml),
                                                                      'MNAME': m.name.upper(),
                                                                      'MVAL': m.id})

def generate_classes(outf, msgs, xml):
    """
    Generate the implementations of the classes representing MAVLink messages.

    """
    print("Generating class definitions")
    wrapper = textwrap.TextWrapper(initial_indent="", subsequent_indent="")
    t.write(outf, "\n${MAVHEAD}.messages = {};\n\n", {'MAVHEAD': get_mavhead(xml)})

    def field_descriptions(fields):
        ret = ""
        for f in fields:
            ret += "                %-18s        : %s (%s)\n" % (f.name, f.description.strip(), f.type)
        return ret

    # now do all the messages
    for m in msgs:

        # assemble some strings we'll use later in outputting ..
        comment = "%s\n\n%s" % (wrapper.fill(m.description.strip()), field_descriptions(m.fields))
        selffieldnames = 'self, '
        for f in m.fields:
            selffieldnames += '%s, ' % f.name
        selffieldnames = selffieldnames[:-2]

        # instance field support copied from mavgen_python
        if m.instance_field is not None:
            instance_field = "'%s'" % m.instance_field
            instance_offset = m.field_offsets[m.instance_field]
        else:
            instance_field = "undefined"
            instance_offset = -1

        # start with the comment block
        outf.write("""
/* 
%s
*/
""" % (comment))

        # function signature + declaration
        outf.write("    %s.messages.%s = function(" % ( get_mavhead(xml), m.name.lower() ) )
        if len(m.fields) != 0:
                outf.write(", ".join(m.fieldnames))
        outf.write(") {")

        # body: set message type properties    
        outf.write("""

    this._format = '%s';
    this._id = %s.MAVLINK_MSG_ID_%s;
    this.order_map = %s;
    this.len_map = %s;
    this.array_len_map = %s;
    this.crc_extra = %u;
    this._name = '%s';

    this._instance_field = %s;
    this._instance_offset = %d;

"""     % (
        m.fmtstr, 
        get_mavhead(xml), 
        m.name.upper(), 
        m.order_map, 
        m.len_map,  
        m.array_len_map, 
        m.crc_extra, 
        m.name.upper(),
        instance_field,
        instance_offset
        ))
        
        # body: set own properties
        if len(m.fieldnames) != 0:
                outf.write("    this.fieldnames = ['%s'];\n" % "', '".join(m.fieldnames))
        outf.write("""

    this.set(arguments,true);

}
""")

        # inherit methods from the base message class
        outf.write("\n%s.messages.%s.prototype = new %s.message;\n" % ( get_mavhead(xml), m.name.lower() ,get_mavhead(xml) ) )

        orderedfields =    "var orderedfields = [ this." + ", this.".join(m.ordered_fieldnames) + "];";


        # Implement the pack() function for this message
        t.write(outf, """
${MAVHEAD}.messages.${MNAME}.prototype.pack = function(mav) {
    ${MORDERED}
    var j = jspack.Pack(this._format, orderedfields);
    if (j === false ) throw new Error("jspack unable to handle this packet");
    return ${MAVHEAD}.message.prototype.pack.call(this, mav, this.crc_extra, j );\n}\n\n""", {'MORDERED': orderedfields, 'MAVHEAD': get_mavhead(xml), 'MNAME': m.name.lower()})

  

def mavfmt(field):
    '''work out the struct format for a type'''
    map = {
        'float'    : 'f',
        'double'   : 'd',
        'char'     : 'c',
        'int8_t'   : 'b',
        'uint8_t'  : 'B',
        'uint8_t_mavlink_version'  : 'B',
        'int16_t'  : 'h',
        'uint16_t' : 'H',
        'int32_t'  : 'i',
        'uint32_t' : 'I',
        'int64_t'  : 'q',
        'uint64_t' : 'Q',
        }

    if field.array_length:
        if field.type in ['char', 'int8_t', 'uint8_t']:
            return str(field.array_length)+'s'
        return str(field.array_length)+map[field.type]
    return map[field.type]

def generate_mavlink_class(outf, msgs, xml):
    print("Generating MAVLink class")

    # Write mapper to enable decoding based on the integer message type
    t.write(outf, "\n\n${MAVHEAD}.map = {\n", {'MAVHEAD': get_mavhead(xml)});
    for m in msgs:
        outf.write("        %s: { format: '%s', type: %s.messages.%s, order_map: %s, crc_extra: %u },\n" % (
            m.id, m.fmtstr, get_mavhead(xml), m.name.lower(), m.order_map, m.crc_extra))
    outf.write("}\n\n")
    
    t.write(outf, """

// Special mavlink message to capture malformed data packets for debugging
${MAVHEAD}.messages.bad_data = function(data, reason) {
    this._id = ${MAVHEAD}.MAVLINK_MSG_ID_BAD_DATA;
    this._data = data;
    this._reason = reason;
    this._msgbuf = data;
}
${MAVHEAD}.messages.bad_data.prototype = new ${MAVHEAD}.message;

/* MAVLink protocol handling class */
${MAVPROCESSOR} = function(logger, srcSystem, srcComponent) {

    this.logger = logger;

    this.seq = 0;
    this.buf = new Buffer.from([]);
    this.bufInError = new Buffer.from([]);
   
    this.srcSystem = (typeof srcSystem === 'undefined') ? 0 : srcSystem;
    this.srcComponent =  (typeof srcComponent === 'undefined') ? 0 : srcComponent;

    this.have_prefix_error = false;

    // The first packet we expect is a valid header, 6 bytes.
    this.protocol_marker = ${PROTOCOL_MARKER};   
    this.expected_length = ${MAVHEAD}.HEADER_LEN;
    this.little_endian = true;

    this.crc_extra = true;
    this.sort_fields = true;
    this.total_packets_sent = 0;
    this.total_bytes_sent = 0;
    this.total_packets_received = 0;
    this.total_bytes_received = 0;
    this.total_receive_errors = 0;
    this.startup_time = Date.now();
    
}

// Implements EventEmitter
util.inherits(${MAVPROCESSOR}, events.EventEmitter);

// If the logger exists, this function will add a message to it.
// Assumes the logger is a winston object.
${MAVPROCESSOR}.prototype.log = function(message) {
    if(this.logger) {
        this.logger.info(message);
    }
}

${MAVPROCESSOR}.prototype.log = function(level, message) {
    if(this.logger) {
        this.logger.log(level, message);
    }
}

${MAVPROCESSOR}.prototype.send = function(mavmsg) {
    buf = mavmsg.pack(this);
    this.file.write(buf);
    this.seq = (this.seq + 1) % 256;
    this.total_packets_sent +=1;
    this.total_bytes_sent += buf.length;
}

// return number of bytes needed for next parsing stage
${MAVPROCESSOR}.prototype.bytes_needed = function() {
    ret = this.expected_length - this.buf.length;
    return ( ret <= 0 ) ? 1 : ret;
}

// add data to the local buffer
${MAVPROCESSOR}.prototype.pushBuffer = function(data) {
    if(data) {
        this.buf = Buffer.concat([this.buf, data]);
        this.total_bytes_received += data.length;
    }
}

// Decode prefix.  Elides the prefix.
${MAVPROCESSOR}.prototype.parsePrefix = function() {

    // Test for a message prefix.
    if( this.buf.length >= 1 && this.buf[0] != this.protocol_marker ) {

        // Strip the offending initial byte and throw an error.
        var badPrefix = this.buf[0];
        this.bufInError = this.buf.slice(0,1);
        this.buf = this.buf.slice(1);
        this.expected_length = ${MAVHEAD}.HEADER_LEN;

        // TODO: enable subsequent prefix error suppression if robust_parsing is implemented
        //if(!this.have_prefix_error) {
        //    this.have_prefix_error = true;
            throw new Error("Bad prefix ("+badPrefix+")");
        //}

    }
    //else if( this.buf.length >= 1 && this.buf[0] == this.protocol_marker ) {
    //    this.have_prefix_error = false;
    //}

}

// Determine the length.  Leaves buffer untouched.
${MAVPROCESSOR}.prototype.parseLength = function() {
    
    if( this.buf.length >= 2 ) {
        var unpacked = jspack.Unpack('BB', this.buf.slice(0, 2));
        this.expected_length = unpacked[1] + ${MAVHEAD}.HEADER_LEN + 2 // length of message + header + CRC
    }

}

// input some data bytes, possibly returning a new message
${MAVPROCESSOR}.prototype.parseChar = function(c) {

    var m = null;

    try {

        this.pushBuffer(c);
        this.parsePrefix();
        this.parseLength();
        m = this.parsePayload();

    } catch(e) {

        this.log('error', e.message);
        this.total_receive_errors += 1;
        m = new ${MAVHEAD}.messages.bad_data(this.bufInError, e.message);
        this.bufInError = new Buffer.from([]);
        
    }

    // emit a packet-specific message as well as a generic message, user/s can choose to use either or both of these.
    if(null != m) {
        this.emit(m._name, m);
        this.emit('message', m);
    }

    return m;

}

${MAVPROCESSOR}.prototype.parsePayload = function() {

    var m = null;

    // If we have enough bytes to try and read it, read it.
    if( this.expected_length >= 8 && this.buf.length >= this.expected_length ) {

        // Slice off the expected packet length, reset expectation to be to find a header.
        var mbuf = this.buf.slice(0, this.expected_length);
        // TODO: slicing off the buffer should depend on the error produced by the decode() function
        // - if a message we find a well formed message, cut-off the expected_length
        // - if the message is not well formed (correct prefix by accident), cut-off 1 char only
        this.buf = this.buf.slice(this.expected_length);
        this.expected_length = 6;

        // w.info("Attempting to parse packet, message candidate buffer is ["+mbuf.toByteArray()+"]");

        try {
            m = this.decode(mbuf);
            this.total_packets_received += 1;
        }
        catch(e) {
            // Set buffer in question and re-throw to generic error handling
            this.bufInError = mbuf;
            throw e;
        }
    }

    return m;

}

// input some data bytes, possibly returning an array of new messages
${MAVPROCESSOR}.prototype.parseBuffer = function(s) {
    
    // Get a message, if one is available in the stream.
    var m = this.parseChar(s);

    // No messages available, bail.
    if ( null === m ) {
        return null;
    }
    
    // While more valid messages can be read from the existing buffer, add
    // them to the array of new messages and return them.
    var ret = [m];
    while(true) {
        m = this.parseChar();
        if ( null === m ) {
            // No more messages left.
            return ret;
        }
        ret.push(m);
    }

}

/* decode a buffer as a MAVLink message */
${MAVPROCESSOR}.prototype.decode = function(msgbuf) {

    var magic, incompat_flags, compat_flags, mlen, seq, srcSystem, srcComponent, unpacked, msgId;

    // decode the header
    try {
        """, {'MAVPROCESSOR': get_mavprocessor(xml),
              'MAVHEAD': get_mavhead(xml),
              'PROTOCOL_MARKER': xml.protocol_marker})
    # Mavlink2 only
    if (xml.protocol_marker == 253):
        t.write(outf, """
unpacked = jspack.Unpack('cBBBBBBHB', msgbuf.slice(0, 10));
        magic = unpacked[0];
        mlen = unpacked[1];
        incompat_flags = unpacked[2];
        compat_flags = unpacked[3];
        seq = unpacked[4];
        srcSystem = unpacked[5];
        srcComponent = unpacked[6];
        var msgIDlow = ((unpacked[7] & 0xFF) << 8) | ((unpacked[7] >> 8) & 0xFF);
        var msgIDhigh = unpacked[8];
        msgId = msgIDlow | (msgIDhigh<<16);
        """, {'MAVHEAD': get_mavhead(xml)})
    # Mavlink1
    else:
        t.write(outf, """
unpacked = jspack.Unpack('cBBBBB', msgbuf.slice(0, 6));
        magic = unpacked[0];
        mlen = unpacked[1];
        seq = unpacked[2];
        srcSystem = unpacked[3];
        srcComponent = unpacked[4];
        msgId = unpacked[5];
        """, {'MAVHEAD': get_mavhead(xml)})

    t.write(outf, """
}
    catch(e) {
        throw new Error('Unable to unpack MAVLink header: ' + e.message);
    }

    if (magic.charCodeAt(0) != this.protocol_marker) {
        throw new Error("Invalid MAVLink prefix ("+magic.charCodeAt(0)+")");
    }

    if( mlen != msgbuf.length - (${MAVHEAD}.HEADER_LEN + 2)) {
        throw new Error("Invalid MAVLink message length.  Got " + (msgbuf.length - (${MAVHEAD}.HEADER_LEN + 2)) + " expected " + mlen + ", msgId=" + msgId);
    }

    if( false === _.has(${MAVHEAD}.map, msgId) ) {
        throw new Error("Unknown MAVLink message ID (" + msgId + ")");
    }

    // decode the payload
    // refs: (fmt, type, order_map, crc_extra) = ${MAVHEAD}.map[msgId]
    var decoder = ${MAVHEAD}.map[msgId];

    // decode the checksum
    try {
        var receivedChecksum = jspack.Unpack('<H', msgbuf.slice(msgbuf.length - 2));
    } catch (e) {
        throw new Error("Unable to unpack MAVLink CRC: " + e.message);
    }

    var messageChecksum = ${MAVHEAD}.x25Crc(msgbuf.slice(1, msgbuf.length - 2));

    // Assuming using crc_extra = True.  See the message.prototype.pack() function.
    messageChecksum = ${MAVHEAD}.x25Crc([decoder.crc_extra], messageChecksum);
    
    if ( receivedChecksum != messageChecksum ) {
        throw new Error('invalid MAVLink CRC in msgID ' +msgId+ ', got 0x' + receivedChecksum + ' checksum, calculated payload checkum as 0x'+messageChecksum );
    }

    var paylen = jspack.CalcLength(decoder.format);
    var payload = msgbuf.slice(${MAVHEAD}.HEADER_LEN, msgbuf.length - 2);

    """, {'MAVPROCESSOR': get_mavprocessor(xml),
          'MAVHEAD': get_mavhead(xml)})

    # Mavlink2 only
    if (xml.protocol_marker == 253):
        t.write(outf, """
//put any truncated 0's back in
    if (paylen > payload.length) {
        payload =  Buffer.concat([payload, Buffer.alloc(paylen - payload.length)]);
    }
""")

    t.write(outf, """
    // Decode the payload and reorder the fields to match the order map.
    try {
        var t = jspack.Unpack(decoder.format, payload);
    }
    catch (e) {
        throw new Error('Unable to unpack MAVLink payload type='+decoder.type+' format='+decoder.format+' payloadLength='+ payload +': '+ e.message);
    }

    // Need to check if the message contains arrays
    var args = {};
    const elementsInMsg = decoder.order_map.length;
    const actualElementsInMsg = JSON.parse(JSON.stringify(t)).length;

    if (elementsInMsg == actualElementsInMsg) {
        // Reorder the fields to match the order map
        _.each(t, function(e, i, l) {
            args[i] = t[decoder.order_map[i]]
        });
    } else {
        // This message contains arrays
        var typeIndex = 1;
        var orderIndex = 0;
        var memberIndex = 0;
        var tempArgs = {};

        // Walk through the fields 
        for(var i = 0, size = decoder.format.length-1; i <= size; ++i) {
            var order = decoder.order_map[orderIndex];
            var currentType =  decoder.format[typeIndex];

            if (isNaN(parseInt(currentType))) {
                // This field is not an array cehck the type and add it to the args
                tempArgs[orderIndex] = t[memberIndex];
                memberIndex++;
            } else {
                // This field is part of an array, need to find the length of the array
                var arraySize = ''
                var newArray = []
                while (!isNaN(decoder.format[typeIndex])) {
                    arraySize = arraySize + decoder.format[typeIndex];
                    typeIndex++;
                }

                // Now that we know how long the array is, create an array with the values
                for(var j = 0, size = parseInt(arraySize); j < size; ++j){
                    newArray.push(t[j+orderIndex]);
                    memberIndex++;
                }

                // Add the array to the args object
                arraySize = arraySize + decoder.format[typeIndex];
                currentType = arraySize;
                tempArgs[orderIndex] = newArray;
            }
            orderIndex++;
            typeIndex++;
        }

        // Finally reorder the fields to match the order map
        _.each(t, function(e, i, l) {
            args[i] = tempArgs[decoder.order_map[i]]
        });
    }

    // construct the message object
    try {
        var m = new decoder.type(args);
        m.set.call(m, args,false);
    }
    catch (e) {
        throw new Error('Unable to instantiate MAVLink message of type '+decoder.type+' : ' + e.message);
    }
    m._msgbuf = msgbuf;
    m._payload = payload
    m.crc = receivedChecksum;
    m._header = new ${MAVHEAD}.header(msgId, mlen, seq, srcSystem, srcComponent, incompat_flags, compat_flags);
    this.log(m);
    return m;
}

""", {'MAVHEAD': get_mavhead(xml), 'MAVPROCESSOR': get_mavprocessor(xml), 'PROTOCOL_MARKER' : xml.protocol_marker})

def generate_footer(outf, xml):
    t.write(outf, """

// Expose this code as a module
module.exports = {${MAVHEAD}, ${MAVPROCESSOR}};

""", {'MAVHEAD': get_mavhead(xml), 'MAVPROCESSOR': get_mavprocessor(xml)})


#--------------------------------------tests start--------

def isfloat(value):
  try:
    float(value)
    return True
  except ValueError:
    return False

def generate_tests_preamble(outf, msgs, args, xml):
    print("Generating preamble")
    t.write(outf, """
/*
TESTS for MAVLink protocol implementation for node.js (auto-generated by mavgen_javascript.py)

Generated from: ${FILELIST}

Note: this file has been auto-generated. DO NOT EDIT
*/
var Long = require('long');

var {${MAVHEAD}, ${MAVPROCESSOR}} = require('./mavlink.js');

// mock mav with sysid-42 and componentid=150
let mav = new ${MAVPROCESSOR}(null, 42, 150);

// this uses the above mock by default, but lets us override it before or during tests if desired
let set_mav = function (_mav) {
    // set global mav var from local
    mav = _mav;
};
exports.set_mav = set_mav;

let verbose = 0; // 0 means not verbose, 1 means a bit more, 2 means most verbose
let set_verbose = function (_v) {
    // set global mav var from local
    verbose = _v;
};
exports.set_verbose = set_verbose;

// relevant to how we pass-in the Long object/s to jspack, we'll assume the calling user is smart enough to know that.
var wrap_long = function (someLong) {
    return [someLong.getLowBitsUnsigned(), someLong.getHighBitsUnsigned()];
}


""", {'FILELIST' : ",".join(args),
      'PROTOCOL_MARKER' : xml.protocol_marker,
      'crc_extra' : xml.crc_extra,
      'WIRE_PROTOCOL_VERSION' : ("2.0" if xml.protocol_marker == 253 else "1.0"),
      'MAVHEAD': get_mavhead(xml),
      'MAVPROCESSOR': get_mavprocessor(xml),
      'HEADERLEN': ("10" if xml.protocol_marker == 253 else "6")}
)


def generate_tests_mavlink_class(outf, msgs, xml):
    print("Generating MAVLink class")

    # Write mapper to enable decoding based on the integer message type
    #t.write(outf, "\n\n${MAVHEAD}.map = {\n", {'MAVHEAD': get_mavhead(xml)});
    for m in msgs:

        outf.write("let test_%s = function () {\n"% (  m.name.lower()));

        #var bs = new mavlink20.messages.battery_status(
        outf.write("   if ( verbose == 2 ) console.log('test creating and packing:%s'); \n" % (  m.name.lower() ) )
        outf.write("   if ( verbose == 1) { process.stdout.write('test creating and packing:"+m.name.lower()+"          \\r'); }\n")
        outf.write("   var test_%s = new %s.messages.%s(); \n" % (  m.name.lower(),get_mavhead(xml), m.name.lower()))
 
        idx = 0; # test data is in same order as ordered_fieldnames
        for f in m.ordered_fieldnames:
            tdata = m.test_data[idx] # test data
            #tdatatype = m.test_data_types[idx] # type of test data 
            fieldtype = m.ordered_fieldtypes[idx] # type of base field
            # wrap things non-number-like as strings, isnumeric() cant handle negatives, but conveniently none of the test suite uses negatives

            #print('testdata:'+tdata);
            #print('tdatatype:'+tdatatype);
            #print('fieldtype:'+fieldtype);
            #if tdatatype != fieldtype:
            #    sys.exit()
            
            _isnum = str(tdata).isdigit()
            _isarray = (tdata[0] == '[')
            _isfloat = isfloat(tdata)

            # javascript inconveniently considers bits >=128 in quite a lot of data types to be unicode, not binary, so we have to understand
            #  these and create them via Buffers and 'binary' or other whacky-doodle-ness here to be sure we get all the tests to pass.

            # array of chars
            if _isarray and (fieldtype == 'char'):
                tdata = 'new Buffer.from('+m.test_data[idx]+').toString("binary")'; # binary encoding here is important for bits >= 128
            # array of uint8_t ( like char )
            elif _isarray and  ( (fieldtype == 'uint8_t') or (fieldtype == 'int8_t')  ):
                tdata = 'new Buffer.from('+m.test_data[idx]+').toString("binary")';  # binary encoding here is important for bits >= 128
            # float/uint16_t/int16_t/int8_t/double array is aparently simple enough without Buffer wrapper
            elif _isarray and ( (fieldtype == 'float') or (fieldtype == 'uint16_t') or (fieldtype == 'int16_t') or (fieldtype == 'double') or ( fieldtype == 'int32_t' ) or ( fieldtype == 'uint32_t' ) ):
                tdata = m.test_data[idx];
            # array of other things
            elif _isarray:
                tdata = 'new Buffer.from('+m.test_data[idx]+') // generic buffer error?';  

            # https://github.com/birchroad/node-jspack/pull/4/commits/9828de064af42ab370009d3eeec7fc11be36b918
            elif fieldtype == 'uint64_t': # unsigned
                tdata =   'wrap_long(Long.fromString("'+m.test_data[idx]+'", true))'; # create unsigned Long from string, then rearrange Long object into 2x32bit unsigned ready for jspack
            elif fieldtype == 'int64_t': # signed
                tdata =   'wrap_long(Long.fromString("'+m.test_data[idx]+'", false))'; # same as above, but signed Long
            # special signed handling, to properly
            elif fieldtype == 'int8_t': # signed fields, we sometimes push raw value/s that exceed the min/max range of signed instead of using the correct sign
                tdata =  '(new Int8Array(['+m.test_data[idx]+']))[0]';  # basically a cast from unsigned int to signed int without sign bit loss
            # special signed handling, to properly
            elif fieldtype == 'int16_t': # signed fields, we sometimes push raw value/s that exceed the min/max range of signed instead of using the correct sign
                tdata =  '(new Int16Array(['+m.test_data[idx]+']))[0]';  # basically a cast from unsigned int to signed int without sign bit loss 
            # special signed handling, to properly 
            elif fieldtype == 'int32_t': # signed fields, we sometimes push raw value/s that exceed the min/max range of signed instead of using the correct sign
                tdata =  '(new Int32Array(['+m.test_data[idx]+']))[0]';  # basically a cast from unsigned int to signed int without sign bit loss

            elif _isfloat:
                    tdata = m.test_data[idx];
            elif _isnum:
                     tdata = m.test_data[idx];   
            else:      
                 #string
                 tdata = '"'+m.test_data[idx]+'"';

            outf.write( "      test_%s.%s = %s;" % ( m.name.lower(),f, tdata) );
            outf.write(" // fieldtype: %s "%(fieldtype));
            outf.write(" isarray: %s \n"%(_isarray));
            idx=idx+1;


        outf.write("   var t = new Buffer.from(test_%s.pack(mav))\n"% (  m.name.lower()));

        outf.write("   return [test_%s,t]; // return an array of unpacked and packed options\n"% (  m.name.lower()));
        outf.write("};\n");
        outf.write("exports.test_%s = test_%s; // expose in module\n"% (  m.name.lower() ,m.name.lower() ) );
        outf.write("\n");
    

    outf.write(get_mavhead(xml)+"""Tests = function(){ \n""")

    for m in msgs:
        outf.write("test_%s();\n"% (  m.name.lower()));

    outf.write("};\n");
   
def generate_tests_footer(outf, xml):
    t.write(outf, """

// if run as an app, run the tests immediately, but if run as a module don't, require user to call
if (require.main === module) {
   verbose=1;  // 0 is not verbose, 1 is a bit, 2 is more.
   ${MAVHEAD}Tests();
} 


/* TESTs for MAVLink protocol handling class */
${MAVPROCESSOR}Tests = function() { mavlink20Tests(); }
exports.${MAVPROCESSOR}Tests = ${MAVPROCESSOR}Tests; // expose in module

""", {'MAVHEAD': get_mavhead(xml), 'MAVPROCESSOR': get_mavprocessor(xml)})



def generate(basename, xml):
    '''generate complete javascript implementation'''

    if basename.endswith('.js'):
        filename = basename
    else:
        filename = basename + '.js'

    msgs = []
    enums = []
    filelist = []
    for x in xml:
        msgs.extend(x.message)
        enums.extend(x.enum)
        filelist.append(os.path.basename(x.filename))


    for m in msgs:
        m.fielddefaults = []
        if xml[0].little_endian:
            m.fmtstr = '<'
        else:
            m.fmtstr = '>'
        m.native_fmtstr = m.fmtstr

        # we've got instance support in generator, but not in the resultant code, yet.
        m.instance_field = None
        for f in m.ordered_fields:
            m.fmtstr += mavfmt(f)
            if f.instance:
                m.instance_field = f.name
                
        m.order_map = [0] * len(m.fieldnames)
        m.len_map = [0] * len(m.fieldnames)
        m.array_len_map = [0] * len(m.fieldnames)
        m.test_data = [0] * len(m.fieldnames)
        m.test_data_types = [0] * len(m.fieldnames)

        for i in range(0, len(m.fieldnames)):
            m.order_map[i] = m.ordered_fieldnames.index(m.fieldnames[i])
            m.ordered_fieldtypes[i] = m.ordered_fieldtypes[i]
            m.test_data[i] = str(m.ordered_fields[i].test_value)
            m.test_data_types[i] = str(m.ordered_fields[i].type)
            m.array_len_map[i] = m.ordered_fields[i].array_length
            
        for i in range(0, len(m.fieldnames)):
            n = m.order_map[i]
            m.len_map[n] = m.fieldlengths[i]





    print("Generating %s" % filename)
    outf = open(filename, "w")
    generate_preamble(outf, msgs, filelist, xml[0])
    generate_enums(outf, enums, xml[0])
    generate_message_ids(outf, msgs, xml[0])
    generate_classes(outf, msgs, xml[0])
    generate_mavlink_class(outf, msgs, xml[0])
    generate_footer(outf, xml[0])
    outf.close()
    print("Generated %s OK" % filename)

    testfilename = filename.replace('.js','.tests.js')
    print("Generating TESTS %s" % testfilename)
    outf = open(testfilename, "w")
    generate_tests_preamble(outf, msgs, filelist, xml[0])
    generate_tests_mavlink_class(outf, msgs, xml[0])
    generate_tests_footer(outf, xml[0])
    outf.close()
    print("Generating TESTS %s" % testfilename)
