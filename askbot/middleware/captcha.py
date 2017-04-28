from django.http import HttpResponse
from PIL import Image, ImageDraw, ImageFont
from cStringIO import StringIO
import random
import base64
import hashlib
import string

def get_md5_value(src):
    myMd5 = hashlib.md5()
    myMd5.update(src)
    myMd5_Digest = myMd5.hexdigest()
    return myMd5_Digest


# make a blank image for the text, initialized to transparent text color


class CaptchaMiddleware(object):

    def process_request(self, request):
        # print request.COOKIES
        if 'robotask' in request.COOKIES and 'robotans' in request.COOKIES:
            ask = request.COOKIES['robotask']
            ans = request.COOKIES['robotans']
            if get_md5_value("_bigbobo_"+ask)[0:8] == ans :
                return None
            
        ask = ''.join(random.choice(string.ascii_letters) for x in range(5))
        ans = get_md5_value("_bigbobo_"+ask)[0:8]
            
            
        txt = Image.new('RGBA', (120, 20), (0,0,0,0))

        # get a font
        fnt = ImageFont.truetype('/usr/share/fonts/dejavu/DejaVuSans.ttf', 20)
        # get a drawing context
        d = ImageDraw.Draw(txt)
        # draw text, full opacity
        #d.text((0,0), get_md5_value("_"+"World")[0:8], font=fnt, fill=(255,255,255,255))
        
        d.text((0,0), ans, font=fnt, fill=(255,255,255,255))

        #out = Image.alpha_composite(base, txt)

        #txt.show()
        imagefile = StringIO() 
        txt.save(imagefile, format='JPEG')
        imagedata = imagefile.getvalue()
        response = HttpResponse("<p>To ensure you are not a robot, please enter the text on the image:</p><input id='ans'/><img src='"+"data:image/jpeg;base64," + base64.b64encode(imagedata)+"' /><input type=button onclick='document.cookie=\"robotans=\"+document.getElementById(\"ans\").value+\";expires=Thu, 01-Jan-2038 00:00:01 GMT;path=/\";window.location.reload();' value=go>")
        response.set_cookie("robotask", ask)
        return response
        # print (request.META['REMOTE_ADDR'])
        # print (request.path)

