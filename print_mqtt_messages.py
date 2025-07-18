import paho.mqtt.client as mqtt, json, sys, datetime as dt
def on_msg(c,u,m):
    print(dt.datetime.now().strftime('%H:%M:%S'),
          m.topic, json.loads(m.payload) if m.payload[0]==123 else m.payload)
mqtt.Client().on_message = on_msg
mqtt.Client().connect("localhost",1883,60).loop_forever()