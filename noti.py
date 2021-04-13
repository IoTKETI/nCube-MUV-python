# -*-coding:utf-8 -*-

"""
 Created by Wonseok Jung in KETI on 2021-03-16.
"""
import json

import thyme, conf, http_app


def parse_sgn(rqi, pc):
    if pc['sgn']:
        if pc['sgn'] is not None:
            nmtype = 'short'
        else:
            nmtype = 'long'
        sgnObj = {}
        cinObj = {}

        if pc['sgn'] is not None:
            sgnObj = pc['sgn']
        else:
            sgnObj = pc['singleNotification']

        if nmtype == 'long':
            print('oneM2M spec. define only short name for resource')
        else:
            if sgnObj.get('sur') is not None:
                if sgnObj['sur'][0] != '/':
                    sgnObj['sur'] = '/' + sgnObj['sur']
                path_arr = sgnObj['sur'].split('/')

            if sgnObj.get('nev') is not None:
                if sgnObj['nev'].get('rep') is not None:
                    if sgnObj['nev']['rep'].get('m2m:cin') is not None:
                        sgnObj['nev']['rep']['cin'] = sgnObj['nev']['rep']['m2m:cin']
                        del sgnObj['nev']['rep']['m2m:cin']

                    if sgnObj['nev']['rep'].get('cin') is not None:
                        cinObj = sgnObj['nev']['rep']['cin']
                    else:
                        print('[mqtt_noti_action] m2m:cin is none')
                        cinObj = None
                else:
                    print(
                        '[mqtt_noti_action] rep tag of m2m:sgn.nev is none. m2m:notification format mismatch with '
                        'oneM2M spec.')
                    cinObj = None
            elif sgnObj.get('sud') is not None:
                print('[mqtt_noti_action] received notification of verification')
                cinObj = {'sud': sgnObj['sud']}
            elif sgnObj.get('vrq') is not None:
                print('[mqtt_noti_action] received notification of verification')
                cinObj = {'vrq': sgnObj['vrq']}
            else:
                print(
                    '[mqtt_noti_action] nev tag of m2m:sgn is none. m2m:notification format mismatch with oneM2M spec.')
                cinObj = None
    else:
        print('[mqtt_noti_action] m2m:sgn tag is none. m2m:notification format mismatch with oneM2M spec.')
        print(pc)

    return path_arr, cinObj, rqi


def response_mqtt(rsp_topic, rsc, to, fr, rqi, inpc, bodytype):
    rsp_message = {}
    rsp_message['m2m:rsp'] = {}
    rsp_message['m2m:rsp']['rsc'] = rsc
    rsp_message['m2m:rsp']['to'] = to
    rsp_message['m2m:rsp']['fr'] = fr
    rsp_message['m2m:rsp']['rqi'] = rqi
    rsp_message['m2m:rsp']['pc'] = inpc

    if bodytype == 'xml':
        pass
    elif bodytype == 'cbor':
        pass
    else:  # json
        thyme.mqtt_client.publish(rsp_topic, json.dumps(rsp_message['m2m:rsp']))


def mqtt_noti_action(topic_arr, jsonObj):
    if jsonObj is not None:
        bodytype = thyme.conf['ae']['bodytype']
        if topic_arr[5] is not None:
            bodytype = topic_arr[5]

        if jsonObj['m2m:rqp']['op'] is None:
            op = ''
        else:
            op = jsonObj['m2m:rqp']['op']
        if jsonObj['m2m:rqp']['to'] is None:
            to = ''
        else:
            to = jsonObj['m2m:rqp']['to']
        if jsonObj['m2m:rqp']['fr'] is None:
            fr = ''
        else:
            fr = jsonObj['m2m:rqp']['fr']
        if jsonObj['m2m:rqp']['rqi'] is None:
            rqi = ''
        else:
            rqi = jsonObj['m2m:rqp']['rqi']
        pc = {}
        if jsonObj['m2m:rqp']['pc'] is None:
            pc = {}
        else:
            pc = jsonObj['m2m:rqp']['pc']

        if pc['m2m:sgn']:
            pc['sgn'] = {}
            pc['sgn'] = pc['m2m:sgn']
            del pc['m2m:sgn']

        path_arr, cinObj, rqi = parse_sgn(rqi, pc)
        if cinObj:
            resp_topic = '/oneM2M/resp/' + topic_arr[3] + '/' + topic_arr[4] + '/' + topic_arr[5]
            response_mqtt(resp_topic, 2001, '', conf.conf["ae"]["id"], rqi, '', topic_arr[5])

            if (cinObj.get("sud") or cinObj.get("vrq")):
                pass
            else:
                print('mqtt ' + bodytype + ' notification <----')
                print('mqtt response - 2001 ---->')

                if http_app.getType(cinObj["con"] == 'string'):
                    thyme.muv_mqtt_client.publish('/'.join(path_arr).replace('/' + path_arr[len(path_arr) - 1], ''),
                                                  cinObj["con"])
                else:
                    thyme.muv_mqtt_client.publish('/'.join(path_arr).replace('/' + path_arr[len(path_arr) - 1], ''),
                                                  json.dumps(cinObj["con"]))
        else:
            print('[mqtt_noti_action] message is not noti')
