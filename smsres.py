from urlrequest import UrlRequest
from datetime import datetime, timedelta
import ipaddress
import time
import os

class ParseSMS():
    def __init__(self,mailapikey:str,webhookbin:str,maildomain:str,allowed_ip:str) -> None:
        self.mailapikey = mailapikey
        self.webhookbin = webhookbin
        self.maildomain = maildomain
        self.allowed_ip = allowed_ip
        self.toggle = 0
        self.poolsend = []
        self.timezone = -4

    def checkip(self, testip:str, allowedips:str):
        return ipaddress.ip_network(testip).subnet_of(ipaddress.ip_network(allowedips))

    def timehours(self, standardtime:str,hours:int):
        return datetime.fromisoformat(standardtime) + timedelta(hours=hours)

    def sendemail(self,emailfrom,emailmessage,emailsubject):
        UrlRequest(
            f"https://api.mailgun.net/v3/{self.maildomain}/messages",
            auth=("api", f"{self.mailapikey}"),
            data={"from": f"{emailfrom}",
                "to": f"SMS@{self.maildomain.removeprefix('sms.')}",
                "subject": f"{emailsubject}",
                "text": f"{emailmessage}"},
                method='POST',callraise=False)

    def run(self):

        try:
            res = UrlRequest(self.webhookbin).json()
        except Exception as error:
            return error

        if res['messid'] is None:

            if self.poolsend and self.toggle >= 5:
                self.sendemail(
                    f"DONE@{self.maildomain}",
                    "\n".join(self.poolsend),
                    "SMS DONE SENDING")
                self.poolsend = []

            self.toggle += 1
            time.sleep(50)
            return (res,self.toggle,self.poolsend)

        if self.checkip(res['headers']['Cf-Connecting-Ip'],self.allowed_ip) is False:
            self.sendemail(
                f"ERROR@{self.maildomain}",
                "IP ERROR",
                f"Sending IP was {res['headers']['Cf-Connecting-Ip']}")
            return (res['headers']['Cf-Connecting-Ip'],self.allowed_ip)

        res = res['content']['data']
        event = res['event_type']
        payload = res['payload']
        text = payload['text']
        to = payload['to'][0]['phone_number'].removeprefix('+1')

        print(res,flush=True)

        if payload['errors']:
            self.sendemail(
                f"ERROR@{self.maildomain}",
                f"{payload['errors']}",
                "ERROR")

        if event == 'message.received':
            fromnr = payload['from']['phone_number'].removeprefix('+1')
            received_at = self.timehours(payload['received_at'],self.timezone).ctime()
            self.sendemail(
                f"{fromnr}@{self.maildomain}",
                f"Message From: {fromnr}\nAt: {received_at}\n{text}",
                "Message Received")
            return (fromnr,text,to,received_at)

        if event == 'message.finalized':
            status = payload['to'][0]['status']
            sent_at = self.timehours(payload['sent_at'],self.timezone).ctime()
            self.poolsend.append(f'{to} - {sent_at} - {status}')
            self.toggle = 0
            return (to,sent_at,status)

if __name__ == '__main__':
    parsesms = ParseSMS(
        mailapikey = os.environ.get('MAIL_API_KEY'),
        webhookbin = os.environ.get('WEBHOOKBIN'),
        maildomain = os.environ.get('MAIL_DOMAIN'),
        allowed_ip = os.environ.get('ALLOWED_IPS'))
    while True:
        log = parsesms.run()
        if log:
            print(log,flush=True)
        time.sleep(10)
