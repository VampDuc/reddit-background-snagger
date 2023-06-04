import getpass  # username
import hashlib
import sys

import magic  # py-magic-bin for mimetypes
import os  # OS things
from PIL import Image  # Image handling
import requests  # GET requests
import time  # Timeouts
# Windows notifications
from win11toast import notify, update_progress, toast

# create the EXE
# pyinstaller --onefile main.py --name=reddit_bg_snagger --icon=Include\snoo.ico -w -F

# Default Configuration
subreddits = [
    "EarthPorn",
    "CityPorn",
    "SkyPorn",
    "WeatherPorn",
    "BotanicalPorn",
    "LakePorn",
    "VillagePorn",
    "BeachPorn",
    "WaterPorn",
    "SpacePorn",
    "wallpapers",
    "wallpaper"
]
save_dest = f"C:\\Users\\{getpass.getuser()}\\Pictures\\Reddit Backgrounds\\"
allowed_timeouts = 5

# set globals
config_location = 'C:\\Reddit Background Snagger'
last_run = 0
toast_popup = False
timeout_counter = 0
min_images = 50
mime = magic.Magic(mime=True)
hashes = []


def make_toast():
    # Create a reusable toast object.
    # Reusing one will ensure only one notification sound fires.
    global toast_popup
    toast_popup = notify(
        progress={
            'title': '',
            'status': '',
            'value': '0',
            'valueStringOverride': ''
        },
        audio='ms-winsoundevent:Notification.Reminder')


def load_config():
    # Load the configuration

    global subreddits
    global allowed_timeouts
    global save_dest
    global min_images
    global last_run

    subs = []
    with open(config_location + '\\config.txt', 'r') as f:
        linesn = f.read()
        lines = linesn.split("\n")
        for line in lines:
            if '|' in line:
                param, value = line.split('|')

                if param == 'save_destination':  # where to save files
                    save_dest = value
                    if value[-1] != chr(92):
                        save_dest += chr(92)
                    if not os.path.exists(save_dest):
                        os.mkdir(save_dest)
                if param == 'max_connect_attempt':  # allowable connection attempts
                    allowed_timeouts = int(value)
                if param == 'subreddit':  # subreddit list
                    subs.append(value)
                if param == 'min_images':
                    min_images = int(value)
                if param == 'last_run':
                    last_run = round(float(value), 0)
    subreddits = subs


def update_config(config, new_value):
    existing = []
    with open(config_location + '\\config.txt', 'r') as f:
        linesn = f.read()
        existing = linesn.split("\n")

    with open(config_location + '\\config.txt', 'w+') as f:
        for line in existing:
            if '|' in line:
                param, value = line.split('|')
                if param == config:
                    f.write(f'{config}|{new_value}' + "\n")
                else:
                    f.write(line + "\n")



def add_to_timeout():
    # update the timeouts between attempts
    global timeout_counter
    timeout_counter = timeout_counter + 1


def reset_timeout():
    # reset timeouts
    global timeout_counter
    timeout_counter = 0


def is_valid_image(full_path):
    # Check if the image to download is worthy

    # no need to delete a file that doesn't exist
    if not os.path.exists(full_path):
        return True

        # Get image dimensions for next steps
    width = 0
    height = 0
    img_hash = False
    try:
        img = Image.open(full_path)
        img_hash = hashlib.md5(Image.open(full_path).tobytes()).digest()
        width = img.width
        height = img.height

        img.close()
    except:
        # Can't open file, remove it
        return False
    print(img_hash)
    print(hashes)
    if img_hash in hashes:  # recently saved; don't save it again
        return False
    if width == 0 or height == 0:  # 0 dimensions either way, invalid
        return False
    if width < height:  # probably portrait aspect
        return False
    if width < 1000 or height < 1000:  # probably too small
        return False
    if width < height * 1.5:  # probably too square
        return False
    if mime.from_file(full_path) != "image/jpeg":  # not a jpeg
        return False

    return True  # assume all others valid


def get_images(sub):
    # Attempt to connect to the front page of the sub; top today and return it as json
    request = requests.get(f"https://www.reddit.com/r/{sub}/top/.json?t=day")
    json = request.json()

    if "message" in json.keys() or request.status_code != 200:
        # The json returned a bad result was an invalid status

        # Wait 5 seconds between attempts to connect
        division = (1 / allowed_timeouts) / 500
        value = (timeout_counter / allowed_timeouts)

        time_counter = 0
        division_adder = 0
        while time_counter < 500:
            time.sleep(.01)
            update_progress({
                'title': f'Connecting to r/{sub}',
                'status': 'Attempting...',
                'value': value,
                'valueStringOverride': f'{timeout_counter + 1} / {allowed_timeouts}'
            })
            value += division
            if value > (timeout_counter / allowed_timeouts) + (1 / allowed_timeouts):
                value = (timeout_counter / allowed_timeouts) + (1 / allowed_timeouts)
            time_counter += 1

        add_to_timeout()
        if timeout_counter < allowed_timeouts:
            return get_images(sub)
        else:
            # out of tries, skip to next sub
            update_progress({
                'value': 1,
                'status': 'Too many timeouts',
                'valueStringOverride': f'{allowed_timeouts} / {allowed_timeouts}'
            })
            reset_timeout()
            return False
    else:  # Successful connection
        reset_timeout()
        time.sleep(.5)
        update_progress({
            'title': f'Getting images from r/{sub}',
            'status': 'Checking posts...',
            'value': 0,
            'valueStringOverride': '',
        })

        posts = json["data"]["children"]
        counter = 1
        saved_images = 0
        json_posts = len(posts)
        for post in posts:
            data = post["data"]

            update_progress({'value': counter / json_posts, 'valueStringOverride': f'{counter}/{json_posts} posts'})

            if data["over_18"] == "True":  # Skip NSFW
                continue
            else:
                image = data["url"]
                basename = os.path.basename(f'{sub}_{data["id"]}.jpg')
                file = f'{save_dest}{basename}'
                if basename != "":
                    skip = False
                    save_image = requests.get(image)
                    try:
                        open(file, 'wb').write(save_image.content)

                    except:
                        skip = True

                    if not is_valid_image(file) or skip:
                        if os.path.exists(file):  # failsafe in case file didn't fail earlier
                            os.remove(file)
                    else:
                        saved_images += 1
            counter += 1

        time.sleep(.5)
        update_progress({'value': 1, 'valueStringOverride': f'{saved_images} valid images saved'})
        time.sleep(.5)
        reset_timeout()


def clear_old_images():
    # Reset the folder for new files
    global hashes
    images = os.listdir(save_dest)
    old_files = {}

    update_progress({
        'title': 'Clearing old images',
        'status': 'Checking...',
        'value': 0,
    })

    for image in images:
        try:
            image_path = os.path.join(save_dest, image)
            if mime.from_file(image_path) == "image/jpeg":
                # Get the list of images in the folder and sort them by timestamp
                old_files[os.path.getmtime(image_path)] = image_path
                # also get the hashes of the current/most recent files
                hashes.append(hashlib.md5(Image.open(image_path).tobytes()).digest())
        except:
            pass

    # No need to continue if we're under the threshold
    # but we want to do the above to get the hashes
    if len(images) <= min_images:
        update_progress({'value': 'Nothing to clean!'})
        return

    timestamps = list(old_files.keys())
    timestamps.sort()
    sorted_files = {i: old_files[i] for i in timestamps}

    update_progress({'value': 'Deleting...'})

    # Remove only the extra files
    counter = len(images)
    toast_counter = 0
    toast_total = counter - min_images
    for i in sorted_files:
        os.remove(f"{sorted_files[i]}")
        time.sleep(.01)
        update_progress(
            {'value': toast_counter / toast_total, 'valueStringOverride': f'{toast_counter}/{toast_total} images'})
        counter -= 1
        toast_counter += 1
        if counter <= min_images:
            break

    time.sleep(.5)
    update_progress(
        {'status': 'Completed!', 'value': 1, 'valueStringOverride': f'{toast_counter}/{toast_total} removed'})


def ensure_setup():
    # Ensure the config exists
    if not os.path.exists(config_location):
        os.mkdir(config_location)
    if not os.path.exists(config_location + '\\config.txt'):
        with open(config_location + '\\config.txt', 'w') as f:
            f.write(f'save_destination|{save_dest}' + "\n")
            f.write(f'max_connection_attempts|{allowed_timeouts}' + "\n")
            f.write(f'min_images|{min_images}' + "\n")
            for sub in subreddits:
                f.write(f'subreddit|{sub}' + "\n")
            f.write(f'last_run|{time.time()}')


def start_application():
    # if we're under 24 hours since last complete run, stop the application
    if last_run < last_run + 86400:
       sys.exit()

    # Give the computer time to wake up and connect to the internet
    # This section happens silently
    time.sleep(300)

    # Make sure reddit is accessible
    try:
        test = requests.get('https://reddit.com')
        result = test.status_code
    except:
        result = 0

    if result != 200:
        if timeout_counter < allowed_timeouts:  # use the same as the config
            add_to_timeout()
            return start_application()  # try again
        else:
            # Reddit is down or there's no internet; finally let the user know.
            toast(f'Could not connect to Reddit', 'Either the server is down, or you do not have internet access.')
            exit()

    reset_timeout()
    return True


if __name__ == '__main__':

    ensure_setup()  # make sure we're good to go
    load_config()  # load the config fresh per run

    start_application()  # ensure reddit is good

    make_toast()  # let the user know we're starting
    clear_old_images()  # clear the old directory

    sub_counter = 0
    for sub in subreddits:  # Start trying to get images
        get_images(sub)
        sub_counter += 1

        # Reddit doesn't really like this, so give it a cooldown between subs.
        if sub_counter < len(subreddits):
            time.sleep(.5)
            update_progress({
                'title': 'Waiting a bit',
                'status': 'Cooling Reddit\'s one server',
                'value': '0',
                'valueStringOverride': 'zzzZZZzzz',
            })

            counter = 0
            sleepy_time = ['z', 'z', 'z', 'Z', 'Z', 'Z', 'z', 'z', 'z', 'Z', 'Z', 'Z']
            while counter < 3000:
                time.sleep(.01)
                s = sleepy_time.pop(0)
                sleepy_time.append(s)
                update_progress({'value': counter / 3000, 'valueStringOverride': ''.join(sleepy_time)})
                counter += 1
            time.sleep(.1)
            update_progress({'value': 1, 'valueStringOverride': f'Naptime over!'})

    # update the last time the application was run
    update_config('last_run', time.time())

