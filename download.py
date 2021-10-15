import youtube_dl
from mutagen import MutagenError
from mutagen.id3 import ID3, TIT2, TPE1, TPUB, TALB, TRCK, TCON
import os
import tkinter
from tkinter import *
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
from datetime import datetime
import json
import shutil # moving files between drives when syncing
import ctypes # prevent sleep mode when downloading
from pprint import pprint

class Globals:
    folder = '' # folder to sync with
    files = []
    current_file = {}
    already_finished = {} # dict of IDs and filenames of videos that are already present in the output folder and where metadata has been set
    dont_delete = [] # list of filenames that are already downloaded but still in the playlist so they shouldn't be deleted when syncing
    start = datetime.now()
    metadata_file = {}

# remove characters that are not allowed in filenames (by windows)
def safe_filename(filename):
    for c in ['\\', '/', ':', '?', '"', '*', '<', '>', '|']:
        filename = filename.replace(c, '')
    return filename

def print_error(process, msg):
    msg = f"[{datetime.now().strftime('%H:%M:%S')}] [{process}] {msg}"
    error_text['state'] = 'normal'
    error_text.insert('end', msg + '\n')
    error_text.see('end')
    error_text['state'] = 'disabled'
    print(msg)
    Tk.update(root)

class Logger(object):
    def debug(self, msg):
        time = f"[{datetime.now().strftime('%H:%M:%S')}] "
        msg = msg.replace('\r', '')
        if '[download]  ' in msg or '[download] 100.0%' in msg:
            if debug.get() == '1':
                error_text['state'] = 'normal'
                error_text.delete('end-1l', 'end')
                error_text.insert('end', '\n' + f'{time}{msg}')
                error_text.see('end')
                error_text['state'] = 'disabled'
            print(f"\r{time}{msg}", end='', flush=True)
        elif '[download] 100%' in msg:
            if debug.get() == '1':
                error_text['state'] = 'normal'
                error_text.delete('end-1l', 'end')
                error_text.insert('end', '\n' + f'{time}{msg}' + '\n')
                error_text.see('end')
                error_text['state'] = 'disabled'
            print(f"\r{time}{msg}")
        else:
            if debug.get() == '1':
                error_text['state'] = 'normal'
                error_text.insert('end', f'{time}{msg}' + '\n')
                error_text.see('end')
                error_text['state'] = 'disabled'
            print(f'{time}{msg}')
        Tk.update(root)

    def warning(self, msg):
        print_error('warning', msg)

    def error(self, msg):
        print_error('error', msg)

def generate_metadata_choices(metadata):
    choices = {}
    
    choices['id'] = metadata['id']
    choices['originaltitle'] = metadata['title']
    
    title_choices = []
    artist_choices = []
    album_choices = []
    track_choices = []

    # add data from metadata.json as first choice
    if metadata['id'] in Globals.metadata_file:
        file_data = Globals.metadata_file[metadata['id']]
        artist_choices.append(file_data['artist'])
        title_choices.append(file_data['title'])
        album_choices.append(file_data['album'])
        track_choices.append(file_data['track'])

    def remove_brackets(text):
        while '(' in text and ')' in text:
            text = text.split('(', 1)[0].strip() + ' ' + text.split(')', 1)[1].strip()
        while '[' in text and ']' in text:
            text = text.split('[', 1)[0].strip() + ' ' + text.split(']', 1)[1].strip()
        for c in ['(', ')', '[', ']']:
            text = text.replace(c, '')
        return text.strip()
    
    if 'track' in metadata:
        track = metadata['track'] if metadata['track'] else ''
        # make only the first letter of each word upper-case if the title is upper-case
        if track.isupper():
            title_choices.append(remove_brackets(track).title())
            title_choices.append(track.title())
        else:
            title_choices.append(remove_brackets(track))
            title_choices.append(track)
        
    if 'artist' in metadata:
        artist = metadata['artist'] if metadata['artist'] else ''
        artist_choices.append(remove_brackets(artist))
        artist_choices.append(artist)

    title = metadata['title']

    for sep in [' - ', ' – ', ' — ', '-', '|', ':', '~', '‐', '_']:
        if sep in title:
            split = title.split(sep)
            for i in range(len(split)):
                title_choices.append(remove_brackets(split[-i-1]))
                title_choices.append(split[-i-1].strip())
                artist_choices.append(remove_brackets(split[i]))
                artist_choices.append(split[i].strip())
            break

    for sep in ['"', '“']:
        if sep in title:
            title_choices.append(title.split(sep)[1])
    
    title_choices.append(remove_brackets(title))
    title_choices.append(title)
    
    if ' by ' in title:
        artist_choices.append(title.split(' by ')[-1].strip())
    
    if len(artist_choices) == 0:
        artist_choices.append(title)

    channel = metadata['channel']
    artist_choices.append(remove_brackets(channel))
    artist_choices.append(channel)

    # Album mode
    if 'album' in metadata:
        album_choices.append(metadata['album'])

    # VGM mode
    if metadata_mode.get() == 'vgm':
        for s in [' OST', ' Soundtrack', ' Original', ' Official', ' Music']:
            artist_choices = [i.replace(s, '').strip() for i in artist_choices]
            title_choices = [i.replace(s, '').strip() for i in title_choices]
    
    if 'playlist' in metadata and metadata['playlist']:
        choices['playlist'] = metadata['playlist']
        album_choices.append(metadata['playlist'])
    if 'playlist_index' in metadata and metadata['playlist_index']:
        choices['playlist_index'] = metadata['playlist_index']
        track_choices.append(metadata['playlist_index'])
    if 'n_entries' in metadata and metadata['n_entries']:
        choices['playlist_length'] = metadata['n_entries']

    # remove empty and duplicate list entries
    choices['title'] = list(dict.fromkeys(filter(None, title_choices)))
    choices['artist'] = list(dict.fromkeys(filter(None, artist_choices)))
    choices['album'] = list(dict.fromkeys(album_choices))
    choices['track'] = list(dict.fromkeys(track_choices))

    return choices
    
def update_combobox(from_start):
    # start at 0 if True / next video if False
    if from_start:
        index = 0
    else:
        index = Globals.files.index(Globals.current_file) + 1
    
    # check if ID at current index is in the loaded metadata and the checkbutton is checked
    while index < len(Globals.files) and Globals.files[index]['id'] in Globals.metadata_file and metadata_file_variable.get() == '1':
        id = Globals.files[index]['id']
        data = Globals.metadata_file[id]
        apply_metadata(id, data)
        index += 1
    
    # reset if end of playlist is reached
    if index < len(Globals.files):
        Globals.current_file = Globals.files[index]
        file = Globals.current_file
        
        video_text = f"Select Metadata for: \"{Globals.current_file['originaltitle']}\""
        if 'playlist_index' in file and 'playlist_length' in file:
            video_text += f" ({file['playlist_index']}/{file['playlist_length']})"
        select_metadata_variable.set(video_text)
        
        if metadata_mode.get() == 'vgm' or metadata_mode.get() == 'album':
            previous_artist = artist_combobox.get()
            previous_album = album_combobox.get()

        if swap_variable.get() == '0':
            artist_combobox['values'] = Globals.current_file['artist']
            title_combobox['values'] = Globals.current_file['title']
            artist_combobox.set(Globals.current_file['artist'][0])
            title_combobox.set(Globals.current_file['title'][0])
        else:
            artist_combobox['values'] = Globals.current_file['title']
            title_combobox['values'] = Globals.current_file['artist']
            artist_combobox.set(Globals.current_file['title'][0])
            title_combobox.set(Globals.current_file['artist'][0])

        # Album mode
        if metadata_mode.get() == 'album':
            album_combobox.set(Globals.current_file['album'][0])
            album_combobox['values'] = Globals.current_file['album']
            track_combobox.set(Globals.current_file['track'][0])
            track_combobox['values'] = Globals.current_file['track']

            if previous_artist:
                if keep_artist_variable.get() == '1':
                    artist_combobox.set(previous_artist)
                artist_combobox['values'] += (previous_artist,)

            if previous_album:
                if keep_artist_variable.get() == '1':
                    album_combobox.set(previous_album)
                album_combobox['values'] += (previous_album,)

        # VGM mode
        if metadata_mode.get() == 'vgm':
                
            album_combobox.set(artist_combobox.get()  + ' OST')
            album_combobox['values'] = [i + ' OST' for i in artist_combobox['values']]

            if previous_artist:
                if keep_artist_variable.get() == '1':
                    artist_combobox.set(previous_artist)
                artist_combobox['values'] += (previous_artist,)

            if previous_album:
                if keep_artist_variable.get() == '1':
                    album_combobox.set(previous_album)
                album_combobox['values'] += (previous_album,)

            track_combobox.set('')
            track_combobox['values'] = []

    else:
        reset()

def apply_metadata(id, data):
    path = os.path.join('out', id + '.mp3')
    filename = safe_filename(f'{data["artist"]} - {data["title"]}.mp3')
        
    try:
        id3 = ID3(path)
        id3.add(TPE1(text=data['artist']))
        id3.add(TIT2(text=data['title']))
        id3.add(TPUB(text=id))

        # Album and VGM Metadata
        if metadata_mode.get() == 'album' or metadata_mode.get() == 'vgm':
            id3.add(TALB(text=data['album']))
            id3.add(TRCK(text=str(data['track'])))

            if metadata_mode.get() == 'vgm':
                id3.add(TCON(text='VGM'))

        id3.save()
        
        os.rename(path, os.path.join('out', filename))
    except MutagenError as e:
        print_error('mutagen', e)
    except OSError as e:
        print_error('OS', e)
    
    Globals.metadata_file[id] = {key: data[key] for key in ['artist', 'title', 'album', 'track']}

def reset():
    # save metadata to file
    with open('metadata.json', 'w') as f:
        json.dump(Globals.metadata_file, f)
    
    # move files to output folder if one has been specified
    if Globals.folder:
        for f in os.listdir('out'):
            try:
                if f.split('.')[-1] == 'mp3':
                    shutil.move(os.path.join('out', f), os.path.join(Globals.folder, f))
                    print_error('sync', f'Moving {f} to output folder')
                else:
                    os.remove(os.path.join('out', f))
                    print_error('sync', f'Deleting {f}')
            except OSError as e:
                print_error('OS', e)
            
    Globals.folder = ''
    Globals.files = []
    Globals.current_file = {}
    Globals.already_finished = {}
    Globals.dont_delete = []
    Globals.metadata_file = {}
    
    url_entry.state(['!disabled'])
    url_entry.delete(0, 'end')
    download_button.state(['!disabled'])
    sync_button.state(['!disabled'])
    sync_folder_variable.set('No folder selected')
    artist_combobox.set('')
    title_combobox.set('')
    artist_combobox['values'] = []
    title_combobox['values'] = []
    progress_text.set('')
    video.set('')
    select_metadata_variable.set('')
    swap_checkbutton.state(['disabled'])
    capitalize_artist_button.state(['disabled'])
    capitalize_title_button.state(['disabled'])
    metadata_auto_button.state(['disabled'])
    metadata_button.state(['disabled'])

    # VGM mode
    if metadata_mode.get() == 'vgm' or metadata_mode.get() == 'album':
        album_combobox.set('')
        album_combobox['values'] = []
        track_combobox.set('')
        track_combobox['values'] = []
        keep_artist_variable.set('0')

def apply_metadata_once():
    file = Globals.current_file
    file['artist'] = artist_combobox.get()
    file['title'] = title_combobox.get()
    file['album'] = album_combobox.get()
    file['track'] = track_combobox.get()
    apply_metadata(file['id'], file)
    update_combobox(False)

def apply_metadata_auto():
    previous_artist = artist_combobox.get()
    previous_album = album_combobox.get()

    for f in Globals.files:
        f['artist'] = f['artist'][0] if keep_artist_variable.get() == '0' else previous_artist
        f['title'] = f['title'][0]
        if metadata_mode.get() == 'vgm':
            f['album'] = f['artist'] + ' OST' if keep_artist_variable.get() == '0' else previous_album
        elif keep_artist_variable.get() == '1':
            f['album'] = previous_album
        else:
            f['album'] = f['album'][0] if f['album'] else ''
        f['track'] = f['track'][0] if f['track'] else ''
        apply_metadata(f['id'], f)
    reset()

def apply_metadata_file():
    if metadata_file_variable.get() == '1' and Globals.current_file and Globals.current_file['id'] in Globals.metadata_file:
        id = Globals.current_file['id']
        data = Globals.metadata_file[id]
        apply_metadata(id, data)
        update_combobox(False)

# download mode dependent methods
# download modes that download files (Download, Sync)
def download():
    # create out folder if it doesn't exist
    try:
        os.mkdir('out')
    except OSError:
        pass
    
    # don't download if the url entry is empty
    if not url_entry.get():
        return
    
    Globals.start = datetime.now()
    
    download_button.state(['disabled'])
    sync_button.state(['disabled'])
    url_entry.state(['disabled'])
    
    # add IDs of already finished files to a list if sync is enabled
    Globals.already_finished = {}
    folder = Globals.folder if download_mode.get() == 'sync' else ''
    if folder:
        for f in os.listdir(folder):
            if f.split('.')[-1] == 'mp3':
                try:
                    id3 = ID3(os.path.join(folder, f))
                    video_id = id3.getall('TPUB')[0].text[0]
                    if video_id:
                        Globals.already_finished[video_id] = f
                except IndexError as e:
                    print(f'{f} has no TPUB-Frame set')

    # load metadata from file
    try:
        with open('metadata.json', 'r') as f:
            Globals.metadata_file = json.load(f)
    except Exception as e:
        print_error('json', e)

    # prevent windows sleep mode
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': 'out/%(id)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3'
        }],
        'ignoreerrors': True,
        'progress_hooks': [hook],
        'match_filter': get_info_dict,
        'logger': Logger(),
        'default_search': 'ytsearch'
    }

    ydl = youtube_dl.YoutubeDL(ydl_opts)
    info = ydl.extract_info(url_entry.get()) # ie_key='Youtube' could be faster
    
    # reset if info is empty
    if not info:
        download_button.state(['!disabled'])
        sync_button.state(['!disabled'])
        url_entry.state(['!disabled'])
        url_entry.delete(0, 'end')
        progress_text.set('')
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
        return
    
    video.set('')
    
    # check which videos haven't been downloaded when downloading a playlist
    if info['webpage_url_basename'] == 'playlist':
        def get_not_downloaded(info):
            results = ''

            for entry in info['entries']:
                if entry['id']:
                    if not os.path.isfile(os.path.join('out', entry['id'] + '.mp3')) and not entry['id'] in Globals.already_finished:
                        results += str(entry["playlist_index"]) + ','

            return results.rstrip(',')
    
        not_downloaded = get_not_downloaded(info)
    
        # try to download all not downloaded videos again
        if not_downloaded:
            print_error('download', f'{(len(not_downloaded) + 1) // 2} videos have not been downloaded. Trying again...')
            ydl_opts['playlist_items'] = not_downloaded
            ydl = youtube_dl.YoutubeDL(ydl_opts)
            ydl.download([url_entry.get()])
    
        not_downloaded = get_not_downloaded(info)
    
        # print IDs of all videos that still couldn't be downloaded
        if not_downloaded:
            print_error('download', f'{(len(not_downloaded) + 1) // 2} videos could not be downloaded. Their indexes are: {not_downloaded}')
    
    progress_bar.set(0)

    time = (datetime.now() - Globals.start).seconds
    progress_text.set(f"Downloaded {len(Globals.files)} video{'s' if len(Globals.files) != 1 else ''} in {time // 60}:{'0' if (time % 60) < 10 else ''}{time % 60}")
    video.set('')
    
    # delete all files from the destination folder that are not in the dont_delete list (which means they were removed from the playlist)
    if Globals.already_finished and Globals.folder:
        for f in Globals.already_finished.values():
            if not f in Globals.dont_delete:
                try:
                    if sync_ask_delete.get() == '0':
                        os.remove(os.path.join(Globals.folder, f))
                        print_error('sync', f'Deleting {f}')
                    elif messagebox.askyesno(title='Delete file?', icon='question', message=f'The video connected to "{f}" is not in the playlist anymore. Do you want to delete the file?'):
                        os.remove(os.path.join(Globals.folder, f))
                        print_error('sync', f'Deleting {f}')
                except OSError as e:
                    print_error('sync', e)
    
    # reactivate windows sleep mode
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)

    # don't start setting metadata if the files list is empty
    if not Globals.files:
        download_button.state(['!disabled'])
        sync_button.state(['!disabled'])
        url_entry.state(['!disabled'])
        url_entry.delete(0, 'end')
        progress_text.set('')
        return
    
    update_combobox(True)
    
    # don't enable metdata selection if everything has been set already
    if Globals.current_file:
        swap_checkbutton.state(['!disabled'])
        capitalize_artist_button.state(['!disabled'])
        capitalize_title_button.state(['!disabled'])
        metadata_auto_button.state(['!disabled'])
        metadata_button.state(['!disabled'])
    else:
        download_button.state(['!disabled'])
        sync_button.state(['!disabled'])
        url_entry.state(['!disabled'])
        url_entry.delete(0, 'end')
        progress_text.set('')

# download modes that download metadata (Calculate length, Download metadata, Backup playlist)
def download_metadata():
    debug.set('1')

    download_button.state(['disabled'])
    url_entry.state(['disabled'])
    
    # prevent windows sleep mode
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)

    ydl_opts = {
        'ignoreerrors': True,
        'logger': Logger(),
        'default_search': 'ytsearch'
    }

    ydl = youtube_dl.YoutubeDL(ydl_opts)
    info = ydl.extract_info(url_entry.get(), download=False) # ie_key='Youtube' could be faster

    # mode dependent actions
    mode = download_mode.get()
    if mode == 'metadata':
        try:
            with open(f'out/{safe_filename(info["title"])}.json', 'w') as f:
                json.dump(info, f)
        except OSError as e:
            print_error('OS', e)
        except Exception as e:
            print_error('Error', e)

    elif mode == 'length':
        def convert_time(sec):
            h = sec // 3600
            min = sec % 3600 // 60
            seconds = sec % 60
            return f'{h}:{"0" if min < 10 else ""}{min}:{"0" if seconds < 10 else ""}{seconds}'

        duration = 0
        playlist = False
        if info['webpage_url_basename'] == 'playlist':
            playlist = True
            for entry in info['entries']:
                if entry:
                    duration += entry['duration']
        elif info['duration']:
            duration = info['duration']

        print_error('length', f'Length of {"playlist" if playlist else "video"} "{info["title"]}": {convert_time(duration)}')

    elif mode == 'backup':
        # make backups folder if it doesn't exist
        try:
            os.mkdir('backups')
        except OSError:
            pass

        # load old file if the playlist has been backed up before
        old_file = {}
        try:
            with open(f'backups/{info["id"]}.json','r') as f:
                old_file = json.load(f)
        except Exception as e:
            print_error('backup', 'No earlier backup found')

        # extract title, uploader and description from info
        new_file = {'title': info['title']}
        if info['webpage_url_basename'] == 'playlist':
            for entry in info['entries']:
                if entry:
                    new_file[entry['id']] = {'title': entry['title'], 'uploader': entry['uploader'], 'description': entry['description']}
        # compare both files if the playlist has been backed up before
        if old_file:
            both = []
            for entry in old_file:
                if entry in new_file:
                    both.append(entry)

            deleted = {k: v for (k, v) in old_file.items() if not k in both}
            added = {k: v for (k, v) in new_file.items() if not k in both}

            if added:
                print_error('backup', f'{len(added)} videos have been added to the playlist:')
                for entry in added.values():
                    print_error('backup', f'{entry["title"]}, {entry["uploader"]}')

            if deleted:
                print_error('backup', f'{len(deleted)} videos have been deleted from the playlist:')
                for entry in deleted.values():
                    print_error('backup', f'{entry["title"]}, {entry["uploader"]}')

            if not added and not deleted:
                print_error('backup', 'No changes found')

            # save changes to file
            changes = {'time': datetime.now().strftime('%Y-%m-%d, %H:%M:%S'),'added': added, 'deleted': deleted}
            changes_file = []
            try:
                with open(f'backups/{info["id"]}_changes.json', 'r') as f:
                    changes_file = json.load(f)
            except Exception as e:
                print_error('backup', e)

            with open(f'backups/{info["id"]}_changes.json', 'w') as f:
                changes_file.append(changes)
                json.dump(changes_file, f)
                print_error('backup', f'Changes have been saved to {f.name}')
        
        # save new data to old file
        with open(f'backups/{info["id"]}.json', 'w') as f:
            json.dump(new_file, f)
            print_error('backup', f'New playlist data has been backed up to {f.name}')

    download_button.state(['!disabled'])
    url_entry.state(['!disabled'])
    url_entry.delete(0, 'end')

    # reactivate windows sleep mode
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)

def hook(d):
    # get current file
    file = Globals.files[-1]
    
    if d['status'] == 'downloading':
        try:
            if 'playlist' in file:
                progress = ((file['playlist_index'] - 1) / file['playlist_length'] + d['downloaded_bytes'] / d['total_bytes'] / file['playlist_length']) * 100
                time = (datetime.now() - Globals.start).seconds
                progress_bar.set(progress)

                progress_text.set(f"Downloading playlist \"{file['playlist']}\", {file['playlist_index']}/{file['playlist_length']} ({round(progress, 1)}% finished, {time // 60}:{'0' if (time % 60) < 10 else ''}{time % 60} elapsed)")
                video.set(f"Current video: {file['originaltitle']}, {d['downloaded_bytes'] * 100 // d['total_bytes']}% finished, {d['eta'] // 60}:{'0' if (d['eta'] % 60) < 10 else ''}{d['eta'] % 60} left")
            else:
                progress_bar.set(d['downloaded_bytes'] / d['total_bytes'] * 100)
                progress_text.set(f"Downloading: {file['originaltitle']}, {round(progress_bar.get())}% finished, {d['eta'] // 60}:{'0' if (d['eta'] % 60) < 10 else ''}{d['eta'] % 60} left")
        except Exception as e: # error for NoneType // int if some values of the dict aren't there yet
            video.set('Downloading...')
    if d['status'] == 'finished':
        if 'playlist' in file:
            video.set('Converting...')
        else:
            progress_text.set('Converting...')
    Tk.update(root)
    
def get_info_dict(info_dict):
    # don't download and don't add to files list if file is already present and metadata has already been set, don't delete that file when syncing
    if info_dict['id'] in Globals.already_finished:
        Globals.dont_delete.append(Globals.already_finished[info_dict['id']])
        print_error('download', f"{info_dict['id']}: File with metadata already present")

        # update progress bar and text

        return f"{info_dict['id']}: File with metadata already present"
    
    file = generate_metadata_choices(info_dict)
    
    # avoid duplicate entries with same ID
    for f in Globals.files:
        if f['id'] == info_dict['id']:
            Globals.files.remove(f)
    
    Globals.files.append(file)
    
    # don't download if file is already present
    if os.path.isfile(os.path.join('out', info_dict['id'] + '.mp3')):
        print_error('download', f"{info_dict['id']}: File already present")
        return f"{info_dict['id']}: File already present"
    
def sync_folder():
    Globals.folder = filedialog.askdirectory()
    sync_folder_variable.set(f'Folder: {Globals.folder}' if Globals.folder else 'No folder selected')
    
def swap():
    temp = artist_combobox.get()
    artist_combobox.set(title_combobox.get())
    title_combobox.set(temp)

    temp = artist_combobox['values']
    artist_combobox['values'] = title_combobox['values']
    title_combobox['values'] = temp

def capitalize_artist():
    artist_combobox.set(artist_combobox.get().title())

def capitalize_title():
    title_combobox.set(title_combobox.get().title())

def update_download_mode():
    for w in download_widgets:
        w.grid_forget()

    mode = download_mode.get()
    if mode == 'download':
        download_button['text'] = 'Download'
        download_button['command'] = download
    elif mode == 'sync':
        sync_button.grid(row=10, column=0, pady=(5, 0), sticky=W)
        sync_label.grid(row=10, column=width // 6, columnspan=width - width // 6, sticky=W)
        sync_ask_delete_checkbutton.grid(row=11, column=0, pady=(5, 0), sticky=W)

        download_button['text'] = 'Download and Sync'
        download_button['command'] = download
    elif mode == 'length':
        download_button['text'] = 'Calculate length'
        download_button['command'] = download_metadata
    elif mode == 'metadata':
        download_button['text'] = 'Download Metadata'
        download_button['command'] = download_metadata
    elif mode == 'backup':
        download_button['text'] = 'Backup Playlist/Search for Changes'
        download_button['command'] = download_metadata

def update_metadata_mode():
    for w in metadata_widgets:
        w.grid_forget()

    mode = metadata_mode.get()

    if mode == 'album' or mode == 'vgm':
        album_label.grid(row=10, column=0, columnspan=width // 6, sticky=W, pady=2)
        album_combobox.grid(row=10, column=width // 6, columnspan=4, sticky=(E, W))
        track_label.grid(row=11, column=0, columnspan=width // 6, sticky=W, pady=2)
        track_combobox.grid(row=11, column=width // 6, columnspan=4, sticky=(E, W))
        keep_artist_checkbutton.grid(row=12, column=0, sticky=W)

        if Globals.current_file:
            file = Globals.current_file
            if mode == 'album':
                album_combobox.set(file['album'][0])
                album_combobox['values'] = file['album']
                track_combobox.set(file['track'][0])
                track_combobox['values'] = file['track']
            elif mode == 'vgm':
                album_combobox.set(artist_combobox.get()  + ' OST')
                album_combobox['values'] = [i + ' OST' for i in artist_combobox['values']]

def artist_combobox_write(*args):
    if metadata_mode.get() == 'vgm':
        artist = artist_combobox.get()
        album_combobox.set(artist if artist.endswith(' OST') else artist + ' OST')

# change current working directory to script location
os.chdir(os.path.dirname(os.path.realpath(__file__)))

root = Tk()
root.title('YouTube to MP3 Converter')
root.geometry('800x720')
root.option_add('*tearOff', FALSE)

download_frame = ttk.Labelframe(root, padding=(3, 10, 12, 12), borderwidth=5, relief='ridge', text='Download')
metadata_frame = ttk.Labelframe(root, padding=(3, 10, 12, 12), borderwidth=5, relief='ridge', text='Metadata')
error_frame = ttk.Labelframe(root, padding=(3, 10, 12, 12), borderwidth=5, relief='ridge', text='Info and Errors')

# menu variables
download_mode = StringVar()
download_mode.set('download')
metadata_mode = StringVar()
metadata_mode.set('normal')
debug = StringVar()
debug.set('0')

# widget variables
sync_folder_variable = StringVar()
sync_folder_variable.set('No folder selected')
sync_ask_delete = StringVar()
sync_ask_delete.set('1')
progress_text = StringVar()
progress_bar = DoubleVar()
video = StringVar()
select_metadata_variable = StringVar()
metadata_file_variable = StringVar()
swap_variable = StringVar()
swap_variable.set('0')
artist_combobox_content = StringVar()

keep_artist_variable = StringVar()
keep_artist_variable.set('0')

# menu
menubar = Menu(root)
root['menu'] = menubar

menu_download_mode = Menu(menubar)
menubar.add_cascade(menu=menu_download_mode, label='Download Mode')
menu_download_mode.add_radiobutton(label='Download', variable=download_mode, value='download', command=update_download_mode)
menu_download_mode.add_radiobutton(label='Sync with Folder', variable=download_mode, value='sync', command=update_download_mode)
menu_download_mode.add_radiobutton(label='Calculate length of Playlist', variable=download_mode, value='length', command=update_download_mode)
menu_download_mode.add_radiobutton(label='Download metadata', variable=download_mode, value='metadata', command=update_download_mode)
menu_download_mode.add_radiobutton(label='Backup Playlist/Search for Changes', variable=download_mode, value='backup', command=update_download_mode)

menu_metadata_mode = Menu(menubar)
menubar.add_cascade(menu=menu_metadata_mode, label='Metadata Mode')
menu_metadata_mode.add_radiobutton(label='Normal', variable=metadata_mode, value='normal', command=update_metadata_mode)
menu_metadata_mode.add_radiobutton(label='Album', variable=metadata_mode, value='album', command=update_metadata_mode)
menu_metadata_mode.add_radiobutton(label='VGM', variable=metadata_mode, value='vgm', command=update_metadata_mode)

menu_debug = Menu(menubar)
menubar.add_cascade(menu=menu_debug, label='Debug')
menu_debug.add_checkbutton(label='Show debug messages', variable=debug, onvalue='1', offvalue='0')

# widgets 
# download widgets
url_label = ttk.Label(download_frame, text='Input video/playlist URL or search query here:')
url_entry = ttk.Entry(download_frame)
sync_label = ttk.Label(download_frame, textvariable=sync_folder_variable)
sync_button = ttk.Button(download_frame, text='Select folder to sync with', command=sync_folder)
download_button = ttk.Button(download_frame, text='Download', command=download)
sync_ask_delete_checkbutton = ttk.Checkbutton(download_frame, text='Ask before deleting files', variable=sync_ask_delete)
progress_label = ttk.Label(download_frame, text='', textvariable=progress_text)
download_progress = ttk.Progressbar(download_frame, orient=HORIZONTAL, mode='determinate', variable=progress_bar)
video_label = ttk.Label(download_frame, text='', textvariable=video)

# download mode dependent widgets
download_widgets = [sync_label, sync_button, sync_ask_delete_checkbutton]

# metadata widgets
select_metadata_label = ttk.Label(metadata_frame, text='', textvariable=select_metadata_variable)
artist_label = ttk.Label(metadata_frame, text='Select the artist:')
title_label = ttk.Label(metadata_frame, text='Select the title:')
artist_combobox = ttk.Combobox(metadata_frame, textvariable=artist_combobox_content)
swap_checkbutton = ttk.Checkbutton(metadata_frame, text='Swap title/artist', command=swap, variable=swap_variable)
title_combobox = ttk.Combobox(metadata_frame)
capitalize_artist_button = ttk.Button(metadata_frame, text='Normal capitalization', command=capitalize_artist, state='disabled')
capitalize_title_button = ttk.Button(metadata_frame, text='Normal capitalization', command=capitalize_title, state='disabled')
metadata_auto_button = ttk.Button(metadata_frame, text='Apply metadata automatically', command=apply_metadata_auto, state='disabled')
metadata_button = ttk.Button(metadata_frame, text='Apply metadata', command=apply_metadata_once, state='disabled')
metadata_file_checkbutton = ttk.Checkbutton(metadata_frame, text='Apply metadata from metadata.json automatically', variable=metadata_file_variable, command=apply_metadata_file)

album_label = ttk.Label(metadata_frame, text='Select the album:')
album_combobox = ttk.Combobox(metadata_frame)
track_label = ttk.Label(metadata_frame, text='Select the track number:')
track_combobox = ttk.Combobox(metadata_frame)
keep_artist_checkbutton = ttk.Checkbutton(metadata_frame, text='Keep artist/album of previous video', variable=keep_artist_variable)

# metadata mode dependent widgets
metadata_widgets = [album_label, album_combobox, track_label, track_combobox, keep_artist_checkbutton]

# error message widgets
error_text = ScrolledText(error_frame, wrap=tkinter.WORD, height=10, state='disabled')

# widget events
artist_combobox_content.trace_add('write', artist_combobox_write)

# grid (rows: 0-9 before mode dependent widgets, 10-19 mode dependent widgets, 20-29 after mode dependent widgets)
width = 6 # number of columns

download_frame.grid(row=0, column=0, sticky=(N, E, W), padx=5, pady=5)
url_label.grid(row=0, column=0, columnspan=width // 6, sticky=W)
url_entry.grid(row=0, column=width // 6, columnspan=5, sticky=(E, W))
download_button.grid(row=20, column=width // 6, pady=(5, 0), sticky=W)
download_progress.grid(row=21, column=0, columnspan=width, sticky=(E, W))
progress_label.grid(row=22, column=0, columnspan=width)
video_label.grid(row=23, column=0, columnspan=width)

metadata_frame.grid(row=1, column=0, sticky=(N, E, W), padx=5, pady=5)
select_metadata_label.grid(row=0, column=0, columnspan=width, sticky=W)
artist_label.grid(row=1, column=0, columnspan=width // 6, sticky=W)
artist_combobox.grid(row=1, column=width // 6, columnspan=4, sticky=(E, W))
capitalize_artist_button.grid(row=1, column=5, padx=5, sticky=W)
swap_checkbutton.grid(row=2, column=width // 6, columnspan=5, sticky=W)
title_label.grid(row=3, column=0, columnspan=width // 6, sticky=W)
title_combobox.grid(row=3, column=width // 6, columnspan=4, sticky=(E, W))
capitalize_title_button.grid(row=3, column=5, padx=5, sticky=W)
metadata_file_checkbutton.grid(row=20, column=0, pady=(5, 0), sticky=W)
metadata_auto_button.grid(row=21, column=0, columnspan=1, pady=(5, 0), sticky=W)
metadata_button.grid(row=21, column=width // 6, columnspan=4, pady=(5, 0), sticky=W)

error_frame.grid(row=2, column=0, sticky=(N, E, W), padx=5, pady=5)
error_text.grid(row=0, column=0, columnspan=width, sticky=(E, W), pady=(5, 0))

url_entry.focus()

root.columnconfigure(0, weight=1)

for f in [download_frame, metadata_frame, error_frame]:
    for i in range(6):
        f.columnconfigure(i, weight=1)

root.mainloop()