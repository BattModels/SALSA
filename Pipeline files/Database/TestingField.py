import hashlib
import string
import base64
import datetime
target_date = datetime.date(2024, 9, 3)
epoch = datetime.date(1970, 1, 1)
print((target_date - epoch).days)
print(epoch + datetime.timedelta(days=19968))