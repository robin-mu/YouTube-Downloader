import youtube_dl
from mutagen import MutagenError
from mutagen.id3 import ID3, TIT2, TPE1, TPUB, TALB, TRCK, TCON
import os
import tkinter
from tkinter import *
from tkinter import filedialog
from tkinter import ttk
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
        print_error('warning', msg)

def generate_metadata_choices(metadata):
    choices = {}
    
    choices['id'] = metadata['id']
    choices['originaltitle'] = metadata['title']
    
    if metadata['playlist']:
        choices['playlist'] = metadata['playlist']
        choices['playlist_index'] = metadata['playlist_index']
        choices['playlist_length'] = metadata['n_entries']
    
    title_choices = []
    artist_choices = []

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

    for sep in [' - ', ' – ', '-', '|', ':', '~', '‐', '_']:
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

    # VGM mode
    if metadata_mode.get() == 'vgm':
        for s in [' OST', ' Soundtrack', ' Original', ' Official', ' Music']:
            artist_choices = [i.replace(s, '').strip() for i in artist_choices]
            title_choices = [i.replace(s, '').strip() for i in title_choices]
    
    # remove empty and duplicate list entries
    choices['title'] = list(dict.fromkeys(filter(None, title_choices)))
    choices['artist'] = list(dict.fromkeys(filter(None, artist_choices)))
    
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
        apply_metadata(id, data[0], data[1])
        index += 1
    
    # reset if end of playlist is reached
    if index < len(Globals.files):
        Globals.current_file = Globals.files[index]
        file = Globals.current_file
        
        video_text = f"Select Metadata for: \"{Globals.current_file['originaltitle']}\""
        if 'playlist' in file:
            video_text += f" ({file['playlist_index']}/{file['playlist_length']})"
        video.set(video_text)
        
        if metadata_mode.get() == 'vgm':
            previous_artist = artist_combobox.get()
            previous_album = vgm_album_combobox.get()

        artist_combobox['values'] = Globals.current_file['artist']
        title_combobox['values'] = Globals.current_file['title']
        artist_combobox.set(Globals.current_file['artist'][0])
        title_combobox.set(Globals.current_file['title'][0])

        # VGM mode
        if metadata_mode.get() == 'vgm':
            if swap_variable.get() == '1':
                artist_combobox['values'] = Globals.current_file['title']
                title_combobox['values'] = Globals.current_file['artist']
                artist_combobox.set(Globals.current_file['title'][0])
                title_combobox.set(Globals.current_file['artist'][0])
                
            vgm_album_combobox.set(artist_combobox.get()  + ' OST')
            vgm_album_combobox['values'] = [i + ' OST' for i in artist_combobox['values']]

            if previous_artist:
                artist_combobox.set(previous_artist)
                artist_combobox['values'] += (previous_artist,)

            if previous_album:
                vgm_album_combobox.set(previous_album)
                vgm_album_combobox['values'] += (previous_album,)

            vgm_track_entry.delete(0, 'end')

    else:
        reset()

def apply_metadata(id, artist, title):
    path = os.path.join('out', id + '.mp3')
    filename = f'{artist} - {title}.mp3'
    
    # remove characters that are not allowed in filenames (by windows)
    for c in ['\\', '/', ':', '?', '"', '*', '<', '>', '|']:
        filename = filename.replace(c, '')
        
    try:
        id3 = ID3(path)
        id3.add(TPE1(text=artist))
        id3.add(TIT2(text=title))
        id3.add(TPUB(text=id))

        # VGM Metadata
        if metadata_mode.get() == 'vgm':
            id3.add(TALB(text=vgm_album_combobox.get()))
            id3.add(TRCK(text=vgm_track_entry.get()))
            id3.add(TCON(text='VGM'))

        id3.save()
        
        os.rename(path, os.path.join('out', filename))
    except MutagenError as e:
        print_error('mutagen', e)
    except OSError as e:
        print_error('OS', e)
    
    Globals.metadata_file[id] = [artist, title]

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
    artist_combobox.set('')
    title_combobox.set('')
    artist_combobox['values'] = []
    title_combobox['values'] = []
    progress.set('')
    video.set('')
    swap_button.state(['disabled'])
    capitalize_artist_button.state(['disabled'])
    capitalize_title_button.state(['disabled'])
    metadata_auto_button.state(['disabled'])
    metadata_button.state(['disabled'])

    # VGM mode
    if metadata_mode.get() == 'vgm':
        vgm_album_combobox.set('')
        vgm_album_combobox['values'] = []
        vgm_track_entry.delete(0, 'end')

def apply_metadata_once():
    apply_metadata(Globals.current_file['id'], artist_combobox.get(), title_combobox.get())
    update_combobox(False)

def apply_metadata_auto():
    for f in Globals.files:
        apply_metadata(f['id'], f['artist'][0], f['title'][0])
    reset()

def apply_metadata_file():
    if metadata_file_variable.get() == '1' and Globals.current_file and Globals.current_file['id'] in Globals.metadata_file:
        id = Globals.current_file['id']
        data = Globals.metadata_file[id]
        apply_metadata(id, data[0], data[1])
        update_combobox(False)

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
    
    # add IDs of already finished files to a list
    Globals.already_finished = {}
    folder = Globals.folder
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
    
    # prevent windows sleep mode
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)

    ydl = youtube_dl.YoutubeDL(ydl_opts)
    info = ydl.extract_info(url_entry.get(), download=True) # ie_key='Youtube' could be faster
    
    # reset if info is empty
    if not info:
        download_button.state(['!disabled'])
        sync_button.state(['!disabled'])
        url_entry.state(['!disabled'])
        url_entry.delete(0, 'end')
        progress.set('')
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
        return
    
    video.set('')
    
    # check which videos haven't been downloaded
    def get_not_downloaded(info):
        results = []

        if '_type' in info:
            if info['_type'] == 'playlist':
                for entry in info['entries']:
                    if entry['id']:
                        if not os.path.isfile(os.path.join('out', entry['id'] + '.mp3')) and not entry['id'] in Globals.already_finished:
                            results.append(entry['id'])
        elif info['id'] and not os.path.isfile(os.path.join('out', info['id'] + '.mp3')) and not info['id'] in Globals.already_finished:
            results.append(info['id'])
        
        return results
    
    not_downloaded = get_not_downloaded(info)
    
    # try to download all not downloaded videos again
    if not_downloaded:
        print_error('download', f'{len(not_downloaded)} videos have not been downloaded. Trying again...')
        ydl.download(not_downloaded)
    
    not_downloaded = get_not_downloaded(info)
    
    # print IDs of all videos that still couldn't be downloaded
    if not_downloaded:
        print_error('download', f'{len(not_downloaded)} videos could not be downloaded:')
        for f in not_downloaded:
            print_error('download', f)
    
    progress_bar.set(0)

    time = (datetime.now() - Globals.start).seconds
    progress.set(f"Downloaded {len(Globals.files)} video{'s' if len(Globals.files) != 1 else ''} in {time // 60}:{'0' if (time % 60) < 10 else ''}{time % 60}")
    
    # delete all files from the destination folder that are not in the dont_download list (which means they were removed from the playlist)
    if Globals.already_finished and Globals.folder:
        for f in Globals.already_finished.values():
            if not f in Globals.dont_delete:
                try:
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
        progress.set('')
        return
    
    # load metadata from file
    try:
        with open('metadata.json', 'r') as f:
            Globals.metadata_file = json.load(f)
    except Exception as e:
        print_error('json', e)
    
    update_combobox(True)
    
    # don't enable metdata selection if everything has been set already
    if Globals.current_file:
        swap_button.state(['!disabled'])
        capitalize_artist_button.state(['!disabled'])
        capitalize_title_button.state(['!disabled'])
        metadata_auto_button.state(['!disabled'])
        metadata_button.state(['!disabled'])
    else:
        download_button.state(['!disabled'])
        sync_button.state(['!disabled'])
        url_entry.state(['!disabled'])
        url_entry.delete(0, 'end')
        progress.set('')

def hook(d):
    # get current file
    file = Globals.files[-1]
    
    if d['status'] == 'downloading':
        try:
            if 'playlist' in file:
                progress_bar.set((file['playlist_index'] - 1) / file['playlist_length'] * 100 + (d['downloaded_bytes'] / d['total_bytes'] * 100) / file['playlist_length'])
                time = (datetime.now() - Globals.start).seconds
                progress.set(f"Downloading playlist \"{file['playlist']}\", {file['playlist_index']}/{file['playlist_length']} ({round(progress_bar.get(), 1)}% finished, {time // 60}:{'0' if (time % 60) < 10 else ''}{time % 60} elapsed)")
                video.set(f"Current video: {file['originaltitle']}, {d['downloaded_bytes'] * 100 // d['total_bytes']}% finished, {d['eta'] // 60}:{'0' if (d['eta'] % 60) < 10 else ''}{d['eta'] % 60} left")
            else:
                progress_bar.set(d['downloaded_bytes'] / d['total_bytes'] * 100)
                progress.set(f"Downloading: {file['originaltitle']}, {round(progress_bar.get())}% finished, {d['eta'] // 60}:{'0' if (d['eta'] % 60) < 10 else ''}{d['eta'] % 60} left")
        except: # error for NoneType // int if some values of the dict aren't there yet
            video.set('Downloading...')
    if d['status'] == 'finished':
        if 'playlist' in file:
            video.set('Converting...')
        else:
            progress.set('Converting...')
    Tk.update(root)
    
def get_info_dict(info_dict):
    # don't download and don't add to files list if file is already present and metadata has already been set, don't delete that file when syncing
    if info_dict['id'] in Globals.already_finished:
        Globals.dont_delete.append(Globals.already_finished[info_dict['id']])
        print_error('download', f"{info_dict['id']}: File with metadata already present")
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
    Globals.folder = tkinter.filedialog.askdirectory()

def swap():
    temp = artist_combobox.get()
    artist_combobox.set(title_combobox.get())
    title_combobox.set(temp)
    
def capitalize_artist():
    artist_combobox.set(artist_combobox.get().title())

def capitalize_title():
    title_combobox.set(title_combobox.get().title())

def swap_permanently():
    temp = artist_combobox.get()
    artist_combobox.set(title_combobox.get())
    title_combobox.set(temp)

    temp = artist_combobox['values']
    artist_combobox['values'] = title_combobox['values']
    title_combobox['values'] = temp

def update_metadata_mode():
    mode = metadata_mode.get()
    if mode == 'normal':
        vgm_album_label.grid_forget()
        vgm_album_combobox.grid_forget()
        vgm_track_label.grid_forget()
        vgm_track_entry.grid_forget()
        vgm_swap_checkbutton.grid_forget()

        swap_button.grid(row=7, column=width // 3, columnspan=width // 3, sticky=(E, W), padx=(5, 5))
    elif mode == 'vgm':
        vgm_album_label.grid(row=9, column=0, columnspan=width // 3)
        vgm_album_combobox.grid(row=10, column=0, columnspan=width // 3, sticky=(E,W))
        vgm_track_label.grid(row=9, column=width // 3 * 2, columnspan=width // 3)
        vgm_track_entry.grid(row=10, column=width // 3 * 2, columnspan=width // 3, sticky=(E,W))
        swap_button.grid_forget()
        vgm_swap_checkbutton.grid(row=7, column=width // 3, columnspan=width // 3, sticky=(E, W), padx=(5, 5))

def artist_combobox_write(*args):
    if metadata_mode.get() == 'vgm':
        artist = artist_combobox.get()
        vgm_album_combobox.set(artist if artist.endswith(' OST') else artist + ' OST')

root = Tk()
root.title('YouTube to MP3 Converter')
root.geometry('900x500')
root.option_add('*tearOff', FALSE)

frame = ttk.Frame(root, padding='3 10 12 12')

# menu variables
metadata_mode = StringVar()
metadata_mode.set('normal')
debug = StringVar()
debug.set('0')

# widget variables
progress = StringVar()
progress_bar = DoubleVar()
video = StringVar()
metadata_file_variable = StringVar()
swap_variable = StringVar()
artist_combobox_content = StringVar()

# menu
menubar = Menu(root)
root['menu'] = menubar

menu_metadata_mode = Menu(menubar)
menubar.add_cascade(menu=menu_metadata_mode, label='Metadata Mode')
menu_metadata_mode.add_radiobutton(label='Normal', variable=metadata_mode, command=update_metadata_mode, value='normal')
menu_metadata_mode.add_radiobutton(label='VGM', variable=metadata_mode, command=update_metadata_mode, value='vgm')
menu_metadata_mode.add_radiobutton(label='Classical', variable=metadata_mode, command=update_metadata_mode, value='classical')

menu_debug = Menu(menubar)
menubar.add_cascade(menu=menu_debug, label='Debug')
menu_debug.add_checkbutton(label='Show debug messages', variable=debug, onvalue='1', offvalue='0')

# widgets
url_label = ttk.Label(frame, text='Input video/playlist URL here:')
url_entry = ttk.Entry(frame)
sync_button = ttk.Button(frame, text='Select folder to sync with', command=sync_folder)
download_button = ttk.Button(frame, text='Download', command=download)
progress_label = ttk.Label(frame, text='', textvariable=progress)
download_progress = ttk.Progressbar(frame, orient=HORIZONTAL, mode='determinate', variable=progress_bar)

video_label = ttk.Label(frame, text='', textvariable=video)
artist_label = ttk.Label(frame, text='Select the artist:')
title_label = ttk.Label(frame, text='Select the title:')
artist_combobox = ttk.Combobox(frame, textvariable=artist_combobox_content)
swap_button = ttk.Button(frame, text='<=>', command=swap, state='disabled')
title_combobox = ttk.Combobox(frame)
capitalize_artist_button = ttk.Button(frame, text='Normal capitalization', command=capitalize_artist, state='disabled')
capitalize_title_button = ttk.Button(frame, text='Normal capitalization', command=capitalize_title, state='disabled')
metadata_auto_button = ttk.Button(frame, text='Apply metadata automatically', command=apply_metadata_auto, state='disabled')
metadata_button = ttk.Button(frame, text='Apply metadata', command=apply_metadata_once, state='disabled')
metadata_file_checkbutton = ttk.Checkbutton(frame, text='Apply metadata from metadata.json', variable=metadata_file_variable, command=apply_metadata_file)
error_text = ScrolledText(frame, wrap=tkinter.WORD, height=10, state='disabled')

vgm_album_label = ttk.Label(frame, text='Select the Album')
vgm_album_combobox = ttk.Combobox(frame)
vgm_track_label = ttk.Label(frame, text='Select the track number')
vgm_track_entry = ttk.Entry(frame)
vgm_swap_checkbutton = ttk.Checkbutton(frame, text='Swap title/artist', command=swap_permanently, variable=swap_variable)

# widget events
artist_combobox_content.trace_add('write', artist_combobox_write)

# grid
width = 6 # number of columns

frame.grid(row=0, column=0, sticky=(N, E, W))
url_label.grid(row=0, column=0, columnspan=width)
url_entry.grid(row=1, column=0, columnspan=width, sticky=(E, W))
sync_button.grid(row=2, column=0, columnspan=width // 3, pady=(5, 0))
download_button.grid(row=2, column=width // 3, columnspan=width // 3, pady=(5, 0))
download_progress.grid(row=3, column=0, columnspan=width, sticky=(E, W))
progress_label.grid(row=4, column=0, columnspan=width)
video_label.grid(row=5, column=0, columnspan=width)

artist_label.grid(row=6, column=0, columnspan=width // 3)
title_label.grid(row=6, column=width // 3 * 2, columnspan=width // 3)
artist_combobox.grid(row=7, column=0, columnspan=width // 3, sticky=(E, W))
swap_button.grid(row=7, column=width // 3, columnspan=width // 3, sticky=(E, W), padx=(5, 5))
title_combobox.grid(row=7, column=width // 3 * 2, columnspan=width // 3, sticky=(E, W))
capitalize_artist_button.grid(row=8, column=0, columnspan=width // 3, padx=(0, 5), pady=(5, 0))
capitalize_title_button.grid(row=8, column=width // 3 * 2, columnspan=width // 3, padx=(5, 0), pady=(5, 0))
metadata_auto_button.grid(row=11, column=0, columnspan=width // 3, pady=(5, 0))
metadata_button.grid(row=11, column=width // 3, columnspan=width // 3, pady=(5, 0))
metadata_file_checkbutton.grid(row=11, column=width // 3 * 2, columnspan=width // 3, pady=(5, 0))
error_text.grid(row=12, column=0, columnspan=width, sticky=(E, W), pady=(5, 0))

url_entry.focus()

root.columnconfigure(0, weight=1)
root.rowconfigure(0, weight=1)
frame.columnconfigure(0, weight=3)
frame.columnconfigure(1, weight=3)
frame.columnconfigure(2, weight=1)
frame.columnconfigure(3, weight=1)
frame.columnconfigure(4, weight=3)
frame.columnconfigure(5, weight=3)

root.mainloop()