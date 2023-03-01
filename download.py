import ctypes  # prevent sleep mode when downloading
import json
import os
import shutil  # moving files between drives when syncing
import subprocess
import tkinter
import webbrowser
from time import sleep
from datetime import datetime
import threading
import queue
from pprint import pprint
from tkinter import *
from tkinter import ttk, filedialog, messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText
from typing import Any, Union
from pydub import AudioSegment

import youtube_dl
from mutagen import MutagenError
from mutagen.id3 import ID3, TIT2, TPE1, TPUB, TALB, TRCK, TCON
from send2trash import send2trash

# change current working directory to script location
os.chdir(os.path.dirname(os.path.realpath(__file__)))


class Globals:
    folder: str = ''  # folder to sync with
    files: dict[str, dict[str, Union[str, list[str]]]] = {}
    metadata_file: dict[str, dict[str, str]] = {}
    library: dict[str, dict[str, dict[str, str]]] = {}
    files_keep: list[
        str] = []  # files whose corresponding videos have been removed from the playlist, but where the file should not be deleted
    num_threads: int = 100
    metadata_selection = None
    metadata_names: list[ttk.Widget] = []
    metadata_selections = queue.Queue()
    metadata_modes = ['normal', 'album', 'vgm', 'classical']
    app = None

    try:
        with open('metadata.json', 'r', encoding='utf-8') as f:
            metadata_file = json.load(f)
        with open('library.json', 'r', encoding='utf-8') as f:
            library = json.load(f)
        with open('files_keep.json', 'r', encoding='utf-8') as f:
            files_keep = json.load(f)
    except Exception as e:
        print('[json]', e)

    classical_work_format_opus: list[str] = ['Barber', 'Beethoven', 'Brahms', 'Chopin', 'Dvořák', 'Grieg',
                                             'Fauré', 'Berlioz', 'Mendelssohn', 'Paganini', 'Prokofiev',
                                             'Rachmaninoff', 'Rimsky-Korsakov', 'Saint-Saëns', 'Clementi',
                                             'Schumann', 'Scriabin', 'Shostakovich', 'Sibelius',
                                             'Eduard Strauss I', 'Johann Strauss I', 'Johann Strauss II',
                                             'Johann Strauss III', 'Josef Strauss', 'Richard Strauss',
                                             'Tchaikovsky', 'Elgar']
    classical_work_format_special: dict[str, str] = {
        'Bach': 'BWV',
        'Händel': 'HWV',
        'Haydn': 'Hob.',
        'Purcell': 'Z.',
        'Mozart': 'K.',
        'Scarlatti': 'K.',
        'Schubert': 'D.'
    }
    classical_work_formats: list[str] = list(dict.fromkeys(['Op.'] + list(classical_work_format_special.values())))
    classical_composers: list[str] = classical_work_format_opus + \
                                     list(classical_work_format_special.keys()) + \
                                     ['Debussy', 'Tarrega', 'Franz von Suppè', 'Bizet', 'Gershwin', 'Verdi',
                                      'Holst', 'Offenbach', 'Khachaturian', 'Delibes', 'Liszt', 'Ravel',
                                      'Rossini', 'Satie', 'Vivaldi', 'Wagner']

    # Consistent names for composers that are spelled in different ways
    classical_composers_real: dict[str, str] = {
        'Dvorak': 'Dvořák',
        'Suppe': 'Franz von Suppè',
        'Suppé': 'Franz von Suppè',
        'Handel': 'Händel',
        'Haendel': 'Händel',
        'Rachmaninov': 'Rachmaninoff',
        'Schostakowitsch': 'Shostakovich',
        'Strauss I': 'Johann Strauss I',
        'Strauss II': 'Johann Strauss II',
        'Strauss Jr.': 'Johann Strauss II',
        'Strauss III': 'Johann Strauss III',
        'Eduard Strauss': 'Eduard Strauss I',
        'Tschaikowsky': 'Tchaikovsky',
        'Faure': 'Fauré'
    }

    classical_types: list[str] = ['Sonata', 'Sonatina', 'Suite', 'Minuet', 'Prelude', 'Fugue', 'Toccata',
                                  'Concerto', 'Symphony', 'Trio', 'Dance', 'Waltz', 'Ballade', 'Etude', 'Impromptu',
                                  'Mazurka', 'Nocturne', 'Polonaise', 'Rondo', 'Scherzo', 'Serenade', 'March',
                                  'Polka', 'Rhapsody', 'Quintet', 'Variations', 'Canon', 'Caprice',
                                  'Moment Musicaux', 'Gymnopédie', 'Gnossienne', 'Ballet']
    classical_types_real: dict[str, str] = {
        'Sonate': 'Sonata',
        'Sonatine': 'Sonatina',
        'Menuett': 'Minuet',
        'Präludium': 'Prelude',
        'Fuge': 'Fugue',
        'Konzert': 'Concerto',
        'Sinfonie': 'Symphony',
        'Tanz': 'Dance',
        'Walzer': 'Waltz',
        'Etüde': 'Etude',
        'Marsch': 'March',
        'Rhapsodie': 'Rhapsody',
        'Quintett': 'Quintet',
        'Variationen': 'Variations',
        'Moment Musical': 'Moment Musicaux',
        'Gymnopedie': 'Gymnopédie',
        'Ballett': 'Ballet'
    }


class MetadataSelection:
    def __init__(self, root: ttk.Widget, metadata: list[dict[str, str | list[str]]], mode: str):
        self.rows = []
        self.vars: list[list[StringVar]] = []
        self.data = metadata
        self.mode: str = mode

        for i, f in enumerate(metadata):
            self.vars.append([StringVar() for _ in range(6)])
            self.rows.append([ttk.Label(root, text=f['originaltitle'], width=50, cursor='hand2'),
                              ttk.Combobox(root, values=f['artist'], textvariable=self.vars[i][0], width=40),
                              ttk.Checkbutton(root, command=lambda row=i: self.capitalize(row, 2), takefocus=0),
                              ttk.Checkbutton(root, command=lambda row=i: self.new_swap(row), takefocus=0),
                              ttk.Combobox(root, values=f['title'], width=50),
                              ttk.Checkbutton(root, command=lambda row=i: self.capitalize(row, 5), takefocus=0),

                              ttk.Combobox(root, values=f['album'], width=30),
                              ttk.Combobox(root, values=f['track'], width=5),
                              ttk.Checkbutton(root, command=lambda row=i: self.previous_artist_album(row), takefocus=0),

                              ttk.Combobox(root, values=f['type'], textvariable=self.vars[i][1], width=20),
                              ttk.Combobox(root, values=f['number'], textvariable=self.vars[i][2], width=5),
                              ttk.Combobox(root, values=f['key'], textvariable=self.vars[i][3], width=5),
                              ttk.Combobox(root, values=f['work'], textvariable=self.vars[i][4], width=20),
                              ttk.Combobox(root, values=f['comment'], textvariable=self.vars[i][5], width=20),
                              ttk.Entry(root, width=30)
                              ])

            self.rows[i][0].bind('<Button-1>', lambda e, id=f['id']: webbrowser.open_new(f'https://youtu.be/{id}'))
            self.rows[i][1].set(f['artist'][0])
            self.rows[i][2].state(['!alternate'])
            self.rows[i][2].bind('<Shift-Button-1>', lambda e, row=i: self.shift(row, 2))
            self.rows[i][3].state(['!alternate'])
            self.rows[i][3].bind('<Shift-Button-1>', lambda e, row=i: self.shift(row, 3))
            self.rows[i][4].set(f['title'][0])
            self.rows[i][5].state(['!alternate'])
            self.rows[i][5].bind('<Shift-Button-1>', lambda e, row=i: self.shift(row, 5))

            self.rows[i][6].set(f['album'][0] if f['album'] else '')
            self.rows[i][7].set(f['track'][0] if f['track'] else '')
            self.rows[i][8].state(['!alternate'])
            self.rows[i][8].bind('<Shift-Button-1>', lambda e, row=i: self.shift(row, 8))

            self.rows[i][9].set(f['type'][0] if f['type'] else '')
            self.rows[i][10].set(f['number'][0] if f['number'] else '')
            self.rows[i][11].set(f['key'][0] if f['key'] else '')
            self.rows[i][12].set(f['work'][0] if f['work'] else '')

            self.rows[i][14].insert(0, Globals.metadata_file[f['id']]['cut'] if f[
                                                                                    'id'] in Globals.metadata_file and 'cut' in
                                                                                Globals.metadata_file[f['id']] else '')

            # probably not necessary
            # if f['file']:
            #     self.rows[i][4].set(f['title'][0])

            for j in range(6):
                self.vars[i][j].trace_add('write', lambda _a, _b, _c, row=i: self.combobox_write(row))

    def capitalize(self, row, column):
        self.rows[row][column - 1].set(self.rows[row][column - 1].get().title())

    def new_swap(self, row):
        temp = self.rows[row][1].get()
        self.rows[row][1].set(self.rows[row][4].get())
        self.rows[row][4].set(temp)

        self.rows[row][1]['values'], self.rows[row][4]['values'] = \
            self.rows[row][4]['values'], self.rows[row][1]['values']

    def shift(self, row, column):
        if self.rows[row][column].instate(['!selected']):
            first_tick = row
            while first_tick >= 0 and not self.rows[first_tick][column].instate(['selected']) and row >= 1:
                first_tick -= 1

            if first_tick != -1:
                for i in range(first_tick + 1, row):
                    self.rows[i][column].state(['selected'])

                    if column in [2, 5]:
                        self.capitalize(i, column)
                    elif column == 3:
                        self.new_swap(i)
                    elif column == 8:
                        self.previous_artist_album(i)

    def grid(self):
        for i, l in enumerate(self.rows):
            for j, w in enumerate(l):
                w.grid_forget()
                if j < 6 or (
                        self.mode == 'album' or self.mode == 'vgm') and j < 9 or self.mode == 'classical' and j >= 9:
                    w.grid(row=i + 1, column=j, sticky='W', padx=1, pady=1)

            current = self.data[i]
            if self.mode == 'album':
                self.rows[i][6].set(current['album'][0] if current['album'] else '')
                self.rows[i][6]['values'] = current['album']

                self.rows[i][7].set(current['track'][0] if current['track'] else '')
                self.rows[i][7]['values'] = current['track']
            elif self.mode == 'vgm':
                self.rows[i][6].set(l[1].get() + ' OST')
                self.rows[i][6]['values'] = [i + ' OST' for i in l[1]['values']]

                self.rows[i][7].set('')
                self.rows[i][7]['values'] = current['track']

    def combobox_write(self, row):
        if self.mode == 'vgm':
            artist: str = self.rows[row][1].get()
            self.rows[row][6].set(artist if artist.endswith(' OST') else artist + ' OST')
        elif self.mode == 'classical':
            artist: str = self.rows[row][1].get()
            type: str = self.rows[row][9].get()
            number: str = self.rows[row][10].get()
            key: str = self.rows[row][11].get()
            work: str = self.rows[row][12].get()
            comment: str = self.rows[row][13].get()

            real_key: str = ''
            real_work: str = ''
            if key:
                real_key = key[0].upper() + ('' if len(key) == 1 else (' Flat' if key[1] == 'b' else ' Sharp')) + \
                           (' Major' if key[0].isupper() else ' Minor')

            if work:
                formats: dict[str, str] = Globals.classical_work_format_special
                work_numbers: list[str] = work.split(' ')
                real_work = ((formats[artist] + ' ') if artist in formats else 'Op. ') + work_numbers[0] + \
                            (((' No. ' if artist != 'Haydn' else ':') + work_numbers[1])
                             if len(work_numbers) > 1 and work_numbers[1] else '') + \
                            ((': ' + ' '.join(work_numbers[2:])) if len(work_numbers) > 2 else '')

            self.rows[row][4].set("{0}{1}{2}{3}{4}".format(type,
                                                           (' No. ' + number) if number else '',
                                                           (' in ' + real_key) if real_key else '',
                                                           (', ' + real_work) if real_work else '',
                                                           ' (' + comment + ')' if comment else ''
                                                           ))

    def previous_artist_album(self, row):
        if row > 0:
            previous_artist = self.rows[row - 1][1].get()
            self.rows[row][1].set(previous_artist)
            self.rows[row][1]['values'] += (previous_artist,)

            previous_album = self.rows[row - 1][6].get()
            self.rows[row][6].set(previous_album)
            self.rows[row][6]['values'] += (previous_album,)

    def reset(self):
        for i, l in enumerate(self.rows):
            for j, w in enumerate(l):
                w.grid_forget()


class LibraryList:
    def __init__(self, root: tkinter.Widget, library_key: str, base_folder: str, default_mode: str, row: int):
        self.root = root
        self.library_key = library_key
        self.base_folder = base_folder
        self.default_mode = default_mode
        self.row = row

        self.library_names = [
            ttk.Label(root, text='Name'),
            ttk.Label(root, text='Videos'),
            ttk.Label(root, text='Synced'),
            ttk.Label(root, text='Link'),
            ttk.Label(root, text='Folder'),
            ttk.Label(root, text='Mode'),
        ]

        self.library_values = [
            Variable(value=list(Globals.library[self.library_key].keys())),
            Variable(value=['' for _ in range(len(Globals.library[self.library_key]))]),
            Variable(value=['' for _ in range(len(Globals.library[self.library_key]))]),
            Variable(value=[e['url'] for e in Globals.library[self.library_key].values()]),
            Variable(value=[e['folder'] for e in Globals.library[self.library_key].values()]),
            Variable(value=[e['metadata_mode'] for e in Globals.library[self.library_key].values()]),
        ] if self.library_key in Globals.library else [Variable(value=[]) for _ in range(6)]

        self.scrollbar = ttk.Scrollbar(self.root, orient=VERTICAL)

        self.library = [
            Listbox(root, selectmode='browse', listvariable=self.library_values[i],
                    height=min(len(Globals.library[self.library_key]), 15) if self.library_key in Globals.library else 10,
                    yscrollcommand=self.scroll) for i in range(len(self.library_values))
        ]

        self.scrollbar['command'] = self.scrollbar_move

        for i in [0, 3, 4, 5]:
            self.library[i].bind('<Double-1>', lambda event, column=i: self.library_change(column))

        self.library_refresh_button = ttk.Button(root, text='Refresh', command=self.library_refresh)
        self.library_sync_button = ttk.Button(root, text='Sync', command=self.library_sync)

        for i, w in enumerate(self.library_names):
            w.grid(row=row * 3, column=i, sticky='ew')

        for i, w in enumerate(self.library):
            w.grid(row=row * 3 + 1, column=i, sticky='ew')

        self.scrollbar.grid(row=row * 3, column=6, sticky='ns', rowspan=2)

        self.library_refresh_button.grid(row=row * 3 + 2, column=0, sticky='ew')
        self.library_sync_button.grid(row=row * 3 + 2, column=1, sticky='ew')

    def scrollbar_move(self, a, b):
        for box in self.library:
            box.yview(a, b)

    def scroll(self, a, b):
        self.scrollbar.set(a, b)
        for box in self.library:
            box.yview('moveto', a)

    def library_refresh(self) -> dict[str, dict[str, str]]:
        # check bookmark file for new playlists
        with open(r'C:\Users\Robin Müller\AppData\Roaming\Opera Software\Opera Stable\Bookmarks', 'r',
                  encoding='utf8') as f:
            file = json.load(f)
            folders = [e for e in file['roots']['custom_root']['userRoot']['children'] if e['name'] == 'Music'][0][
                'children']
            urls = [[e['url'] for e in f['children']] for f in folders if f['name'] == self.library_key][0]
            new = [url for url in urls if url not in self.library_values[3].get()]
            print(new)

        ydl = youtube_dl.YoutubeDL({'logger': Logger()})

        for url in new:
            info = ydl.extract_info(url, process=False)
            title = info['title']
            if self.library_key not in Globals.library:
                Globals.library[self.library_key] = {}

            if self.default_mode == 'album':
                video_info = ydl.extract_info(list(info['entries'])[0]['url'], process=False)
                title = video_info['artist'].split(',')[0] + ' - ' + title[8:]
            Globals.library[self.library_key][title] = {'url': url,
                                                        'folder': self.base_folder + '/' + safe_filename(title),
                                                        'metadata_mode': self.default_mode}
            self.__init__(self.root, self.library_key, self.base_folder, self.default_mode, self.row)

        out = {}
        for i in range(len(self.library_values[3].get())):
            url = self.library_values[3].get()[i]
            folder = self.library_values[4].get()[i]
            mode = self.library_values[5].get()[i]
            downloaded_ids = []

            if folder and os.path.isdir(folder):
                for f in os.listdir(folder):
                    if os.path.join(folder, f) not in Globals.files_keep and f.split('.')[-1] == 'mp3':
                        try:
                            id3 = ID3(os.path.join(folder, f))
                            video_id = id3.getall('TPUB')[0].text[0]
                            if video_id:
                                downloaded_ids.append(video_id)
                        except IndexError:
                            print(f'[Debug] {f} has no TPUB-Frame set')

            info = ydl.extract_info(url, process=False)
            playlist_ids = [e['id'] for e in info['entries']]

            not_downloaded_urls = [e for e in playlist_ids if e not in downloaded_ids]
            print(f'Not downloaded: {not_downloaded_urls}')
            if sorted(playlist_ids) != sorted(downloaded_ids):
                out[url] = {'folder': folder, 'mode': mode}

            synced = list(self.library_values[2].get())
            synced[i] = 'Yes' if all([e in downloaded_ids for e in playlist_ids]) else 'No'
            self.library_values[2].set(synced)

            videos = list(self.library_values[1].get())
            videos[i] = f'Playlist: {len(playlist_ids)}, Downloaded: {len([e for e in playlist_ids if e in downloaded_ids])}, in Folder: {len(downloaded_ids)}'
            self.library_values[1].set(videos)

        pprint(out)
        return out

    def library_change(self, column=None):
        listbox = self.library[column]
        sel = listbox.curselection()

        if sel:
            row = sel[0]
            new = list(self.library_values[column].get())
            key = self.library_values[0].get()[row]
            if column in [0, 3, 5]:
                prompt = simpledialog.askstring('New value', 'Enter a new value')
                if prompt:
                    new[row] = prompt

                    if column == 0:
                        Globals.library[self.library_key][prompt] = Globals.library[self.library_key][key]
                        Globals.library[self.library_key].pop(key, None)
                    elif column == 3:
                        Globals.library[self.library_key][key]['url'] = prompt
                    elif column == 5:
                        Globals.library[self.library_key][key]['metadata_mode'] = prompt
            else:
                prompt = filedialog.askdirectory()
                new[row] = prompt or ''

                Globals.library[self.library_key][key]['folder'] = prompt or ''

            self.library_values[column].set(new)

    def library_sync(self):
        to_download = self.library_refresh()
        Globals.app.download_mode.set('sync')

        download_thread = threading.Thread(target=lambda: download(to_download))
        download_thread.start()

        Globals.app.notebook.select(0)

        while download_thread.is_alive():
            Tk.update(Globals.app.root)

        Globals.app.enable_metadata_selection()


class App:
    def __init__(self):
        self.root = Tk()
        self.root.title('YouTube to MP3 Converter')
        self.root.geometry('800x720')
        self.root.option_add('*tearOff', FALSE)
        self.root.protocol("WM_DELETE_WINDOW", self.on_exit)

        # menu variables
        self.download_mode = StringVar()
        self.download_mode.set('download')
        self.metadata_mode = StringVar()
        self.metadata_mode.set('normal')
        self.debug = StringVar()
        self.debug.set('0')

        # widget variables
        self.url_variable = StringVar()
        self.output_folder_variable = StringVar()
        self.output_folder_variable.set('Folder: Default (click to open)')
        self.sync_ask_delete = StringVar()
        self.sync_ask_delete.set('1')
        self.progress_text = StringVar()
        self.progress_bar = DoubleVar()

        # menu
        self.menubar = Menu(self.root)
        self.root['menu'] = self.menubar

        self.menu_download_mode = Menu(self.menubar)
        self.menubar.add_cascade(menu=self.menu_download_mode, label='Download Mode')
        self.menu_download_mode.add_radiobutton(label='Download', variable=self.download_mode, value='download',
                                                command=self.update_download_mode)
        self.menu_download_mode.add_radiobutton(label='Sync with Folder', variable=self.download_mode, value='sync',
                                                command=self.update_download_mode)
        self.menu_download_mode.add_radiobutton(label='Calculate length of Playlist', variable=self.download_mode,
                                                value='length',
                                                command=self.update_download_mode)
        self.menu_download_mode.add_radiobutton(label='Download metadata', variable=self.download_mode,
                                                value='metadata',
                                                command=self.update_download_mode)
        self.menu_download_mode.add_radiobutton(label='Backup Playlist/Search for Changes', variable=self.download_mode,
                                                value='backup',
                                                command=self.update_download_mode)

        self.menu_metadata_mode = Menu(self.menubar)
        self.menubar.add_cascade(menu=self.menu_metadata_mode, label='Metadata Mode')
        self.menu_metadata_mode.add_radiobutton(label='Normal', variable=self.metadata_mode, value='normal',
                                                command=self.update_metadata_selection)
        self.menu_metadata_mode.add_radiobutton(label='Album', variable=self.metadata_mode, value='album',
                                                command=self.update_metadata_selection)
        self.menu_metadata_mode.add_radiobutton(label='VGM', variable=self.metadata_mode, value='vgm',
                                                command=self.update_metadata_selection)
        self.menu_metadata_mode.add_radiobutton(label='Classical', variable=self.metadata_mode, value='classical',
                                                command=self.update_metadata_selection)

        self.menu_debug = Menu(self.menubar)
        self.menubar.add_cascade(menu=self.menu_debug, label='Debug')
        self.menu_debug.add_checkbutton(label='Show debug messages', variable=self.debug, onvalue='1', offvalue='0')
        self.menu_debug.add_command(label='Reset', command=self.reset)
        self.menu_debug.add_command(label='Test', command=self.test)

        # widgets
        # Notebook
        self.notebook = ttk.Notebook(self.root, takefocus=0)

        # Download tab
        self.download_tab = ttk.Frame()
        self.notebook.add(self.download_tab, text='Download')

        self.download_frame = ttk.Labelframe(self.download_tab, padding=(3, 10, 12, 12), borderwidth=5, relief='ridge',
                                             text='Download')

        self.metadata_labelframe = ttk.Labelframe(self.download_tab, padding=(3, 10, 12, 12), borderwidth=5,
                                                  relief='ridge',
                                                  text='Metadata')

        self.error_frame = ttk.Labelframe(self.download_tab, padding=(3, 10, 12, 12), borderwidth=5, relief='ridge',
                                          text='Info and Errors')

        # download widgets
        self.url_label = ttk.Label(self.download_frame,
                                   text='Input video/playlist URL, search query or saved URL name:')
        self.url_combobox = ttk.Combobox(self.download_frame, values=list(Globals.library['Playlists'].keys()),
                                         textvariable=self.url_variable)
        self.save_url_button = ttk.Button(self.download_frame, text='Save...', command=self.save_url)
        self.output_folder_label = ttk.Label(self.download_frame, textvariable=self.output_folder_variable,
                                             cursor='hand2')
        self.output_folder_button = ttk.Button(self.download_frame, text='Select output folder...',
                                               command=self.select_output_folder)
        self.download_button = ttk.Button(self.download_frame, text='Download',
                                          command=self.download)
        self.sync_ask_delete_checkbutton = ttk.Checkbutton(self.download_frame, text='Ask before deleting files',
                                                           variable=self.sync_ask_delete)
        self.progress_label = ttk.Label(self.download_frame, text='', textvariable=self.progress_text)
        self.download_progress = ttk.Progressbar(self.download_frame, orient=HORIZONTAL, mode='determinate',
                                                 variable=self.progress_bar)

        # download widgets that get enabled/disabled
        self.download_widgets = [self.url_combobox, self.save_url_button, self.output_folder_button,
                                 self.download_button]

        # download mode dependent widgets
        self.download_mode_widgets = [self.sync_ask_delete_checkbutton]

        # metadata widgets
        self.metadata_canvas = Canvas(self.metadata_labelframe)
        self.metadata_scrollbar = ttk.Scrollbar(self.metadata_labelframe, orient=VERTICAL,
                                                command=self.metadata_canvas.yview)
        self.metadata_frame = ttk.Frame(self.metadata_canvas)

        self.metadata_canvas.configure(yscrollcommand=self.metadata_scrollbar.set)
        self.metadata_canvas.create_window((0, 0), window=self.metadata_frame, anchor="nw")

        self.generate_metadata_names(self.metadata_frame)

        self.metadata_button = ttk.Button(self.metadata_labelframe, text='Apply metadata',
                                          command=self.apply_all_metadata,
                                          state='disabled')

        # error message widgets
        self.error_text = ScrolledText(self.error_frame, wrap=tkinter.WORD, height=10, state='disabled')

        # Library tab
        self.library_tab = ttk.Frame()
        self.notebook.add(self.library_tab, text='Library')

        LibraryList(self.library_tab, 'Playlists', 'D:/Musik', 'normal', 0)
        LibraryList(self.library_tab, 'Alben', 'D:/Musik/Alben', 'album', 1)
        LibraryList(self.library_tab, 'Später Anhören Alben', 'D:/Musik/Später Anhören Alben', 'album', 2)

        # widget events
        self.url_variable.trace_add('write', self.url_combobox_write)
        self.output_folder_label.bind('<Button-1>', self.open_output_folder)

        self.metadata_canvas.bind('<MouseWheel>', self.scroll)
        self.metadata_frame.bind('<Configure>',
                                 lambda e: self.metadata_canvas.configure(
                                     scrollregion=self.metadata_canvas.bbox("all")))

        # grid (rows: 0-9 before mode dependent widgets, 10-19 mode dependent widgets, 20-29 after mode dependent widgets)
        self.width = 6  # number of columns

        self.notebook.grid(sticky='NESW')

        self.download_frame.grid(row=0, column=0, sticky='NEW', padx=5, pady=5)
        self.url_label.grid(row=0, column=0, columnspan=self.width // 6, sticky='W')
        self.url_combobox.grid(row=0, column=self.width // 6, columnspan=4, sticky='EW')
        self.save_url_button.grid(row=0, column=self.width - self.width // 6, columnspan=self.width // 6, padx=(5, 0),
                                  sticky='W')
        self.output_folder_button.grid(row=1, column=0, pady=(5, 0), sticky='W')
        self.output_folder_label.grid(row=1, column=self.width // 6, columnspan=self.width - self.width // 6,
                                      sticky='W')
        self.download_button.grid(row=20, column=self.width // 6, pady=(5, 0), sticky='W')
        self.download_progress.grid(row=21, column=0, columnspan=self.width, pady=5, sticky='EW')
        self.progress_label.grid(row=22, column=0, columnspan=self.width)

        self.metadata_labelframe.grid(row=1, column=0, sticky='NEW', padx=5, pady=5)
        self.metadata_canvas.pack(side=LEFT, expand=True, fill=X)
        self.metadata_scrollbar.pack(side=RIGHT, fill=Y)
        self.metadata_button.pack(before=self.metadata_canvas, side=BOTTOM, anchor='w')

        self.error_frame.grid(row=2, column=0, sticky='NEW', padx=5, pady=5)
        self.error_text.grid(row=0, column=0, columnspan=self.width, sticky='EW', pady=(5, 0))

        self.url_combobox.focus()

        for f in [self.root, self.download_tab]:
            f.columnconfigure(0, weight=1)

        for f in [self.download_frame, self.metadata_labelframe, self.error_frame, self.library_tab]:
            for i in range(6):
                f.columnconfigure(i, weight=1)

        self.root.bind('<Configure>', self.size_changed)

    def generate_metadata_names(self, widget):
        Globals.metadata_names = [ttk.Label(widget, text='Video title'),
                                  ttk.Label(widget, text='Artist'),
                                  ttk.Label(widget, text=''),
                                  ttk.Label(widget, text='Swap'),
                                  ttk.Label(widget, text='Title'),
                                  ttk.Label(widget, text=''),

                                  ttk.Label(widget, text='Album'),
                                  ttk.Label(widget, text='Track'),
                                  ttk.Label(widget, text='Previous'),

                                  ttk.Label(widget, text='Type'),
                                  ttk.Label(widget, text='Number'),
                                  ttk.Label(widget, text='Key'),
                                  ttk.Label(widget, text='Work'),
                                  ttk.Label(widget, text='Comment'),
                                  ttk.Label(widget, text='Cut')
                                  ]

    def mainloop(self):
        self.root.mainloop()

    # menu click methods
    def update_download_mode(self):
        for w in self.download_mode_widgets:
            w.grid_forget()

        match self.download_mode.get():
            case 'download':
                self.output_folder_button['text'] = 'Select output folder'
                self.download_button['text'] = 'Download'
                self.download_button['command'] = self.download
                self.output_folder_button.grid(row=1, column=0, pady=(5, 0), sticky='W')
                self.output_folder_label.grid(row=1, column=self.width // 6, columnspan=self.width - self.width // 6,
                                              sticky='W')
            case 'sync':
                self.output_folder_button['text'] = 'Select folder to sync with'
                self.sync_ask_delete_checkbutton.grid(row=11, column=0, pady=(5, 0), sticky='W')

                self.download_button['text'] = 'Download and Sync'
                self.download_button['command'] = self.download
            case 'length':
                self.download_button['text'] = 'Calculate length'
                self.download_button['command'] = download_metadata
            case 'metadata':
                self.download_button['text'] = 'Download Metadata'
                self.download_button['command'] = download_metadata
            case 'backup':
                self.download_button['text'] = 'Backup Playlist/Search for Changes'
                self.download_button['command'] = download_metadata

    def update_metadata_selection(self):
        if Globals.metadata_selection:
            for i, name in enumerate(Globals.metadata_names):
                name.grid_forget()
                if i < 6 or (self.metadata_mode.get() == 'album' or self.metadata_mode.get() == 'vgm') \
                        and i < 9 or self.metadata_mode.get() == 'classical' and i >= 9:
                    name.grid(row=0, column=i)
                    name.bind('<MouseWheel>', self.scroll)

            Globals.metadata_selection.mode = self.metadata_mode.get()
            Globals.metadata_selection.grid()

            for l in Globals.metadata_selection.rows:
                for w in l:
                    w.bind('<MouseWheel>', self.scroll)

    # GUI methods
    def enable_widgets(self, widgets: list[ttk.Widget] | ttk.Widget) -> None:
        if type(widgets) == list:
            for w in widgets:
                w.state(['!disabled'])
        else:
            widgets.state(['!disabled'])

    def disable_widgets(self, widgets: list[ttk.Widget] | ttk.Widget) -> None:
        if type(widgets) == list:
            for w in widgets:
                w.state(['disabled'])
        else:
            widgets.state(['disabled'])

    def disable_download_widgets(self):
        self.disable_widgets(self.download_widgets)

    def download(self):
        url = self.url_combobox.get()
        if not url:
            return

        url = Globals.library['Playlists'][url]['url'] if url in Globals.library['Playlists'] else url

        # disable download widgets
        self.disable_download_widgets()

        download_thread = threading.Thread(
            target=lambda url=url, folder=Globals.folder, mode=self.metadata_mode: download(
                {url: {'folder': folder, 'mode': mode}}))
        download_thread.start()

        while download_thread.is_alive():
            Tk.update(self.root)

        # reset if the files dict is empty (no metadata to be set)
        if not Globals.files:
            self.reset()
            return

        self.enable_metadata_selection()

    def enable_metadata_selection(self):
        for e in [[Globals.files[k] for k in Globals.files if Globals.files[k]['mode'] == mode] for mode in Globals.metadata_modes]:
            if e:
                Globals.metadata_selections.put(e)

        selection = Globals.metadata_selections.get()
        self.metadata_mode.set(selection[0]['mode'])

        Globals.metadata_selection = MetadataSelection(self.metadata_frame, selection, selection[0]['mode'])
        self.update_metadata_selection()
        self.enable_widgets(self.metadata_button)

    def apply_all_metadata(self):
        for i, file in enumerate(Globals.metadata_selection.data):
            file['artist'] = Globals.metadata_selection.rows[i][1].get()
            file['title'] = Globals.metadata_selection.rows[i][4].get()

            if self.metadata_mode.get() == 'album' or self.metadata_mode.get() == 'vgm':
                file['album'] = Globals.metadata_selection.rows[i][6].get()
                file['track'] = Globals.metadata_selection.rows[i][7].get()
            else:
                file['album'] = ''
                file['track'] = ''

            if self.metadata_mode.get() == 'classical' and Globals.metadata_selection.rows[i][14].get().strip():
                file['cut'] = Globals.metadata_selection.rows[i][14].get()

            apply_metadata(file['id'], file)

        if not Globals.metadata_selections.empty():
            selection = Globals.metadata_selections.get()
            pprint(selection)
            self.metadata_mode.set(selection[0]['mode'])

            Globals.metadata_selection.reset()
            Globals.metadata_selection = MetadataSelection(self.metadata_frame, selection, selection[0]['mode'])
            self.update_metadata_selection()
        else:
            self.reset()

    def save_url(self):
        url = simpledialog.askstring(title='Save URL',
                                     prompt='Input the name under which to save the URL and settings:')
        if url:
            Globals.library['Playlists'][url] = {'url': self.url_combobox.get(), 'folder': Globals.folder,
                                                 'metadata_mode': self.metadata_mode.get()}
        self.url_combobox['values'] = list(Globals.library['Playlists'].keys())

    def select_output_folder(self):
        Globals.folder = filedialog.askdirectory()
        self.output_folder_variable.set(
            'Folder: ' + (Globals.folder if Globals.folder else 'Default') + ' (click to open)')

    def open_output_folder(self, event):
        if Globals.folder:
            folder = Globals.folder.replace('/', "\\")
            subprocess.run(f'explorer.exe "{folder}"')
        else:
            subprocess.run('explorer.exe out')

    def reset(self):
        # save metadata to file
        with open('metadata.json', 'w') as f:
            json.dump(Globals.metadata_file, f)

        # save saved urls to file
        with open('library.json', 'w') as f:
            json.dump(Globals.library, f)

        with open('files_keep.json', 'w', encoding='utf-8') as f:
            json.dump(Globals.files_keep, f)

        # move files to output folder
        for f in os.listdir('out'):
            try:
                if f.split('.')[-1] == 'mp3':
                    try:
                        id3 = ID3(os.path.join('out', f))
                        video_id = id3.getall('TPUB')[0].text[0]
                        if video_id:
                            if not os.path.isdir(Globals.files[video_id]['folder']):
                                os.mkdir(Globals.files[video_id]['folder'])

                            shutil.move(os.path.join('out', f), os.path.join(Globals.files[video_id]['folder'], f))
                            self.print_info('sync', f'Moving {f} to {Globals.files[video_id]["folder"]}')
                    except IndexError as e:
                        print(f'[Debug] {f} can not be moved: ' + str(e))
                else:
                    os.remove(os.path.join('out', f))
                    self.print_info('sync', f'Deleting {f}')
            except OSError as e:
                self.print_info('OS', e)

        # reset globals
        Globals.folder = ''
        Globals.files = {}

        # reset widgets
        self.disable_widgets(self.metadata_button)
        if Globals.metadata_selection:
            Globals.metadata_selection.reset()
            Globals.metadata_selection = None
        for w in Globals.metadata_names:
            w.grid_forget()

        self.enable_widgets(self.download_widgets)
        self.url_combobox.set('')
        self.progress_text.set('')
        self.output_folder_variable.set('Folder: Default (click to open)')

    # track exit of program
    def on_exit(self):
        self.reset()
        self.root.destroy()

    # event methods
    # track changes of comboboxes to update other comboboxes
    def url_combobox_write(self, *args):
        if (url := self.url_combobox.get()) in Globals.library['Playlists']:
            Globals.folder = Globals.library['Playlists'][url]['folder']
            self.output_folder_variable.set(
                'Folder: ' + (Globals.folder if Globals.folder else 'Default') + ' (click to open)')

            self.metadata_mode.set(Globals.library['Playlists'][url]['metadata_mode'])
            self.update_metadata_selection()

    # track change of window size
    def size_changed(self, event):
        try:
            self.error_text['height'] = (self.root.winfo_height() - self.download_frame.winfo_height() -
                                         self.metadata_labelframe.winfo_height() - 80) // 16
        except NameError:
            pass

    def scroll(self, event):
        self.metadata_canvas.yview_scroll(int(-1 * (event.delta / 40)), UNITS)
        return 'break'

    def update_progress(self, progress_percent, progress_text):
        try:
            self.progress_bar.set(progress_percent)
            self.progress_text.set(progress_text)
        except Exception as e:
            self.print_info("GUI", e)
            self.progress_text.set('Downloading...')

        Tk.update(self.root)

    def print_download_info(self, msg: str):
        time = f"[{datetime.now().strftime('%H:%M:%S')}] "
        msg = msg.replace('\r', '')
        self.error_text['state'] = 'normal'
        if '[download]  ' in msg or '[download] 100.0%' in msg:
            if self.debug.get() == '1':
                self.error_text.delete('end-1l', 'end')
                self.error_text.insert('end', '\n' + f'{time}{msg}')
            print(f"\r{time}{msg}", end='', flush=True)
        elif '[download] 100%' in msg:
            if self.debug.get() == '1':
                self.error_text.delete('end-1l', 'end')
                self.error_text.insert('end', '\n' + f'{time}{msg}' + '\n')
            print(f"\r{time}{msg}")
        else:
            if self.debug.get() == '1':
                self.error_text.insert('end', f'{time}{msg}' + '\n')
            print(f'{time}{msg}')
        self.error_text.see('end')
        self.error_text['state'] = 'disabled'

        Tk.update(self.root)

    def print_info(self, process: str, msg):
        msg = f"[{datetime.now().strftime('%H:%M:%S')}] [{process}] {msg}"
        self.error_text['state'] = 'normal'
        self.error_text.insert('end', msg + '\n')
        self.error_text.see('end')
        self.error_text['state'] = 'disabled'
        print(msg)
        Tk.update(self.root)

    def get_url_combobox(self):
        return self.url_combobox.get()

    def get_download_mode(self):
        return self.download_mode.get()

    def get_metadata_mode(self):
        return self.metadata_mode.get()

    def test(self):
        download({'https://www.youtube.com/playlist?list=PL77J9_Azlrw9_te4dOoqaY3nt8KCa3dbS': {'folder': 'Test',
                                                                                               'mode': 'normal'},
                  'https://www.youtube.com/playlist?list=PL77J9_Azlrw_mxM8z03ukfNaq9483ssk0': {'folder': 'testest',
                                                                                               'mode': 'normal'}})
        self.enable_metadata_selection()


class Logger(object):
    def debug(self, msg):
        Globals.app.print_download_info(msg)

    def warning(self, msg):
        Globals.app.print_info('warning', msg)

    def error(self, msg):
        Globals.app.print_info('error', msg)


# remove characters that are not allowed in filenames (by windows)
def safe_filename(filename: str) -> str:
    for c in ['\\', '/', ':', '?', '"', '*', '<', '>', '|']:
        filename = filename.replace(c, '')
    return filename


# convert number of seconds to string with format minutes:seconds
def sec_to_min(sec: int) -> str:
    return f"{sec // 60}:{'0' if (sec % 60) < 10 else ''}{sec % 60}"


def generate_metadata_choices(metadata: dict[str, Any], mode: str) -> dict[str, Union[str, list[str]]]:
    choices = {'id': metadata['id'], 'originaltitle': metadata['title']}

    title_choices: list[str] = []
    artist_choices: list[str] = []
    album_choices: list[str] = []
    track_choices: list[str] = [Globals.files[metadata['id']]['playlist_index']] if 'playlist_index' in Globals.files[metadata['id']] else []

    # add data from metadata.json as first choice
    choices['file'] = False
    if metadata['id'] in Globals.metadata_file:
        choices['file'] = True
        file_data: dict[str, str] = Globals.metadata_file[metadata['id']]
        artist_choices.append(file_data['artist'])
        title_choices.append(file_data['title'])
        album_choices.append(file_data['album'])
        track_choices.append(file_data['track'])

    def remove_brackets(text: str) -> str:
        for b in ['()', '[]']:
            while b[0] in text and b[1] in text:
                split: list[str] = text.split(b[0], 1)
                text = split[0].strip() + ' ' + \
                       (split[1].split(b[1], 1)[1].strip() if b[1] in split[1] else split[1].strip())
        for c in ['(', ')', '[', ']']:
            text = text.replace(c, '')
        return text.strip()

    # get title and artist set by YouTube Music
    if 'track' in metadata:
        track: str = metadata['track'] if metadata['track'] else ''
        # make only the first letter of each word upper-case if the title is upper-case
        if track.isupper():
            title_choices.append(remove_brackets(track).title())
            title_choices.append(track.title())
        else:
            title_choices.append(remove_brackets(track))
            title_choices.append(track)

    if 'artist' in metadata and metadata['artist']:
        artist = metadata['artist']
        artist_choices.append(artist.split(',')[0])
        artist_choices.append(remove_brackets(artist))
        artist_choices.append(artist)

    # get title and artist from video title and channel name
    title: str = metadata['title']

    for sep in [' - ', ' – ', ' — ', '-', '|', ':', '~', '‐', '_', '∙']:
        if sep in title:
            split: list[str] = title.split(sep)
            for i in range(len(split)):
                title_choices.append(remove_brackets(split[-i - 1]))
                title_choices.append(split[-i - 1].strip())
                artist_choices.append(remove_brackets(split[i]))
                artist_choices.append(split[i].strip())

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
    if mode == 'vgm':
        for s in [' OST', ' Soundtrack', ' Original', ' Official', ' Music']:
            artist_choices = [i.replace(s, '').strip() for i in artist_choices]
            title_choices = [i.replace(s, '').strip() for i in title_choices]

    # Classical mode
    def lower_and_remove_symbols(text: str) -> str:
        for s in ['.', ',', '(', ')', '/', '#', '[', ']', ':']:
            text = text.replace(s, ' ')
        return text.lower().strip()

    composer_choices: list[str] = []
    type_choices: list[str] = []
    number_choices: list[str] = []
    key_choices: list[str] = []
    work_choices: list[str] = []
    comment_choices: list[str] = ([title.split('"')[1]] if title.count('"') >= 2 else []) + \
                                 [i.split(')')[0] for i in title.split('(') if ')' in i] if '(' in title else []
    if mode == 'classical':
        # look for known composer in title, but spelled differently
        for c in Globals.classical_composers_real:
            if c.lower() in title.lower():
                composer_choices.append(Globals.classical_composers_real[c])
        for c in Globals.classical_composers:
            if c.lower() in title.lower() and c not in composer_choices:
                composer_choices.append(c)
        for c in artist_choices:
            composer_choices.append(c)

        # type choices
        for c in Globals.classical_types_real:
            if c.lower() in title.lower():
                type_choices.append(Globals.classical_types_real[c])
        for c in Globals.classical_types:
            if c.lower() in title.lower() and c not in type_choices:
                type_choices.append(c)
        for c in title_choices:
            type_choices.append(c)

        # number choices
        split: list[str] = lower_and_remove_symbols(title).split()
        for i in range(len(split)):
            if split[i].isnumeric() and split[i - 1] not in [f.lower().replace('.', '') for f in
                                                             Globals.classical_work_formats]:
                number_choices.append(split[i])

        # key choices
        if ' in ' in title:
            text: str = title.split(' in ')[-1]
            key: str = text[0]
            if key.lower() in 'abcdefgh':
                text = text.lower()
                if 'major' in text or 'dur' in text:
                    key = key.upper()
                elif 'minor' in text or 'moll' in text:
                    key = key.lower()

                if 'sharp' in text or len(text) > 2 and text[1:2] == 'is' or len(text) > 1 and text[1] == '#':
                    key += 's'
                elif 'flat' in text or len(text) > 2 and (text[1] == 's' or text[1:2] == 'es') or len(text) > 1 and (
                        text[1] == 'b' or text[1] == '♭'):
                    key += 'b'

                key_choices.append(key)

        # work choices
        title_lower: str = lower_and_remove_symbols(title)
        for w in [' ' + f.lower().replace('.', '') + ' ' for f in Globals.classical_work_formats]:
            if w in title_lower:
                words: list[str] = title_lower.split(w)[-1].split()

                if words[0] not in ['major', 'minor', 'flat', 'sharp']:
                    work: str = words[0].upper() if words[0].isalpha() else words[0]
                    if len(words) > 2 and words[1] == 'no':
                        work += ' ' + (words[2].upper() if words[2].isalpha() else words[2])
                    work_choices.append(work)

    if 'playlist' in metadata and metadata['playlist']:
        album_choices.append(metadata['playlist'])
    if 'playlist_index' in metadata and metadata['playlist_index']:
        track_choices.append(metadata['playlist_index'])

    # remove empty and duplicate list entries
    choices['title'] = list(dict.fromkeys(filter(None, title_choices)))
    choices['artist'] = list(
        dict.fromkeys(
            filter(None, composer_choices if mode == 'classical' else artist_choices)))
    choices['album'] = list(dict.fromkeys(album_choices))
    choices['track'] = list(dict.fromkeys(track_choices))
    choices['type'] = list(dict.fromkeys(type_choices))
    choices['number'] = list(dict.fromkeys(number_choices))
    choices['key'] = list(dict.fromkeys(key_choices))
    choices['work'] = list(dict.fromkeys(work_choices))
    choices['comment'] = list(dict.fromkeys(comment_choices))

    return choices


# download mode dependent methods
# download modes that download files (Download, Sync)
# urls: dict with url: folder and mode
def download(urls: dict[str, dict[str, str]]) -> list[str]:
    # create out folder if it doesn't exist
    try:
        os.mkdir('out')
    except OSError:
        pass

    start = datetime.now()
    out: list[str] = []  # list of ids on which metadata has to be set

    # add IDs of already finished files to a list
    # dict of IDs and filenames of videos that are already present in the output folder and where metadata has been set
    already_finished: dict[str, str] = {}
    for folder in [e['folder'] for e in urls.values() if 'folder' in e and e['folder']]:
        if os.path.isdir(folder):
            for f in os.listdir(folder):
                if f.split('.')[-1] == 'mp3':
                    try:
                        id3 = ID3(os.path.join(folder, f))
                        video_id = id3.getall('TPUB')[0].text[0]
                        if video_id:
                            already_finished[video_id] = os.path.join(folder, f)
                    except IndexError:
                        print(f'[Debug] {f} has no TPUB-Frame set')

    # prevent windows sleep mode
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)

    def get_info_dict(info_dict):
        id = info_dict['id']
        Globals.files[id].update(generate_metadata_choices(info_dict, Globals.files[id]['mode']))
        out.append(info_dict['id'])

        # don't download if file is already present
        if os.path.isfile(os.path.join('out', info_dict['id'] + '.mp3')):
            Globals.app.print_info('download', f"{info_dict['id']}: File already present")
            return f"{info_dict['id']}: File already present"

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': 'out/%(id)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3'
        }],
        'match_filter': get_info_dict,
        'logger': Logger(),
        'default_search': 'ytsearch'
    }

    ydl = youtube_dl.YoutubeDL(ydl_opts)
    video_queue = queue.Queue()
    # list of ids that are already downloaded but still in the playlist, so they shouldn't be deleted when syncing
    dont_delete: list[str] = []

    def download_video(video_id):
        try:
            ydl.extract_info('https://youtu.be/' + video_id)
        except youtube_dl.DownloadError as e:
            Globals.app.print_info('multithreading_download', e)
            video_queue.put(video_id)

    def threading_worker():
        while True:
            try:
                id = video_queue.get(block=False)
                download_video(id)
                video_queue.task_done()
            except queue.Empty:
                break

    for url in urls:
        # obtain info to decide between video or playlist download
        info = {}
        while True:
            try:
                info = ydl.extract_info(url, process=False)
                break
            except youtube_dl.DownloadError as e:
                Globals.app.print_info('download', str(e) + " (Trying again)")
                continue

        if info:
            # playlist
            if info['webpage_url_basename'] == 'playlist':
                entries = list(info['entries'])
                all_ids = [e['id'] for e in entries]

                dont_delete += [e['id'] for e in entries if e['id'] in already_finished]
                ids = [e['id'] for e in entries if e['id'] not in already_finished]

                for id in ids:
                    Globals.files[id] = {'folder': urls[url]['folder'], 'mode': urls[url]['mode'],
                                         'playlist_index': all_ids.index(id) + 1}
                    video_queue.put(id)
            # video
            else:
                Globals.files[info['id']] = {'folder': urls[url]['folder'], 'mode': urls[url]['mode']}
                video_queue.put(info['id'])

    total_length = video_queue.qsize()

    threads = []
    for i in range(Globals.num_threads):
        t = threading.Thread(target=threading_worker)
        t.start()
        threads.append(t)

    while active_threads := len([t for t in threads if t.is_alive()]):
        queue_length = video_queue.qsize()
        videos_done = total_length - queue_length - active_threads

        progress = videos_done / total_length * 100
        progress_text = f'Downloading {total_length} videos with {active_threads} threads' + \
                        f', {videos_done}/{total_length} ({round(progress, 1)}%) finished, ' \
                        f'{sec_to_min((datetime.now() - start).seconds)} elapsed'

        Globals.app.update_progress(progress, progress_text)
        sleep(0.1)

    # delete all files from the destination folder that are not in the dont_delete list
    # (which means they were removed from the playlist) (only in sync mode)
    if already_finished and Globals.app.get_download_mode() == 'sync':
        for id in already_finished:
            filename = already_finished[id]
            if id not in dont_delete and filename not in Globals.files_keep:
                try:
                    if Globals.app.sync_ask_delete.get() == '0' or messagebox.askyesno(title='Delete file?',
                                                                                       icon='question',
                                                                                       message=f'The video connected to "{filename}" '
                                                                                               f'is not in the playlist '
                                                                                               f'anymore. Do you want to '
                                                                                               f'delete the file?'):
                        os.remove(filename)
                        Globals.app.print_info('sync', f'Deleting {filename}')
                    else:
                        Globals.files_keep.append(filename)
                except OSError as e:
                    Globals.app.print_info('sync', e)

    Globals.app.update_progress(0, f"Downloaded {len(Globals.files)} video{'s' if len(Globals.files) != 1 else ''} in "
                                   f"{sec_to_min((datetime.now() - start).seconds)}")

    # reactivate windows sleep mode
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)

    return out


def apply_metadata(id, data):
    path = os.path.join('out', id + '.mp3')
    filename = os.path.join('out', safe_filename(f'{data["artist"]} - {data["title"]}.mp3'))

    # cut mp3 in classical mode
    if 'cut' in data:
        # create file with cut information
        try:
            with open('cut.info', 'w') as f:
                # format example: 3+5 1:30+4-1:40 2:30+5
                # cut out from 0:00 to 0:05, 1:30 to 1:40 and 2:30 to end of file, add 3 seconds of silence to the
                # beginning, 4 seconds after the cut from 1:30 to 1:40 and 5 seconds to the end

                highest: int = 0
                for cut in data['cut'].split('-'):  # ['3+5 1:30+4', '1:40 2:30+5']
                    split_space: list[str] = cut.split(' ')  # a) ['3+5', '1:30+4'] b) ['1:40', '2:30+5']

                    if '+' in split_space[0]:  # true for a), false for b)
                        split_plus: list[str] = split_space[0].split('+')  # a) ['3', '5']
                        if int(split_plus[0]) > highest:
                            highest = int(split_plus[0])
                        f.write("file 's.mp3'\n")
                        f.write(f'outpoint {split_plus[0]}\n')  # outpoint 3

                        f.write(f"file '{path}'\n")
                        if split_plus[1]:
                            f.write(f'inpoint {split_plus[1]}\n')  # inpoint 5
                    else:
                        f.write(f"file '{path}'\n")
                        if split_space[0]:
                            f.write(f'inpoint {split_space[0]}\n')  # inpoint 1:40

                    if len(split_space) == 2 and split_space[1]:
                        if '+' in split_space[1]:
                            split_plus: list[str] = split_space[1].split('+')  # a) ['1:30', '4'] b) ['2:30', '5']
                            if split_plus[0]:
                                f.write(f'outpoint {split_plus[0]}\n')

                            if int(split_plus[1]) > highest:
                                highest = int(split_plus[1])
                            f.write("file 's.mp3'\n")
                            f.write(f'outpoint {split_plus[1]}\n')
                        else:
                            f.write(f'outpoint {split_space[1]}\n')

            if highest > 0:
                subprocess.run(f'ffmpeg.exe -filter_complex '
                               f'anullsrc=sample_rate={AudioSegment.from_mp3(path).frame_rate} -t {highest} s.mp3')

            # run ffmpeg to cut the file
            subprocess.run(f'ffmpeg.exe -f concat -safe 0 -i cut.info -c copy "{filename}"')
            send2trash(path)
            if highest > 0:
                os.remove('s.mp3')
            path = filename
        except Exception as e:
            Globals.app.print_info('cut', e)

    try:
        id3 = ID3(path)
        id3.add(TPE1(text=data['artist']))
        id3.add(TIT2(text=data['title']))
        id3.add(TPUB(text=id))

        # Album and VGM Metadata
        if Globals.app.get_metadata_mode() == 'album' or Globals.app.get_metadata_mode() == 'vgm':
            id3.add(TALB(text=data['album']))
            id3.add(TRCK(text=str(data['track'])))

        # Genre based on metadata mode
        genres: dict[str, str] = {'vgm': 'VGM', 'classical': 'Klassik'}
        if Globals.app.get_metadata_mode() in genres:
            id3.add(TCON(text=genres[Globals.app.get_metadata_mode()]))

        id3.save()

        if 'cut' not in data:
            os.rename(path, filename)
    except MutagenError as e:
        Globals.app.print_info('mutagen', e)
    except OSError as e:
        Globals.app.print_info('OS', e)

    Globals.metadata_file[id] = {key: data[key] for key in ['artist', 'title', 'album', 'track']}
    if 'cut' in data:
        Globals.metadata_file[id]['cut'] = data['cut']
        send2trash('cut.info')


# download modes that download metadata (Calculate length, Download metadata, Backup playlist)
def download_metadata():
    Globals.app.debug.set('1')

    Globals.app.disable_download_widgets()

    # prevent windows sleep mode
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)

    mode = Globals.app.get_download_mode()
    url = Globals.app.get_url_combobox()
    ydl_opts = {
        'ignoreerrors': True,
        'logger': Logger(),
        'default_search': 'ytsearch'
    }

    ydl = youtube_dl.YoutubeDL(ydl_opts)
    info = ydl.extract_info(Globals.library['Playlists'][url]['url'] if url in Globals.library['Playlists'] else url,
                            download=False,
                            process=mode == 'metadata')

    if info:
        # mode dependent actions
        match mode:
            case 'metadata':
                try:
                    with open(f'out/{safe_filename(info["title"])}.json', 'w') as f:
                        json.dump(info, f)
                except OSError as e:
                    Globals.app.print_info('OS', e)
                except Exception as e:
                    Globals.app.print_info('download_metadata', e)

            case 'length':
                def convert_time(sec):
                    h = int(sec // 3600)
                    min = int(sec % 3600 // 60)
                    seconds = int(sec % 60)
                    return f'{h}:{"0" if min < 10 else ""}{min}:{"0" if seconds < 10 else ""}{seconds}'

                try:
                    playlist = info['webpage_url_basename'] == 'playlist'
                    duration = sum([i['duration'] for i in list(info['entries'])]) if playlist else info['duration']

                    Globals.app.print_info('length',
                                           f'Length of {"playlist" if playlist else "video"} "{info["title"]}": '
                                           f'{convert_time(duration)}')
                except KeyError as e:
                    Globals.app.print_info('length', e)

            case 'backup':
                # make backups folder if it doesn't exist
                try:
                    os.mkdir('backups')
                except OSError:
                    pass

                # load old file if the playlist has been backed up before
                old_file: dict[str, dict[str, str]] = {}
                try:
                    with open(f'backups/{info["id"]}.json', 'r') as f:
                        old_file = json.load(f)
                except FileNotFoundError:
                    Globals.app.print_info('backup', 'No earlier backup found')

                # extract title, uploader and description from info
                new_file: dict[str, dict[str, str]] = {'title': info['title']}
                if info['webpage_url_basename'] == 'playlist' and 'entries' in info and info['entries']:
                    for entry in list(info['entries']):
                        if entry:
                            new_file[entry['id']] = {'title': entry['title'], 'uploader': entry['uploader']}

                # compare both files if the playlist has been backed up before
                if old_file:
                    both = [e for e in old_file if e in new_file]
                    deleted = {k: v for (k, v) in old_file.items() if k not in both}
                    added = {k: v for (k, v) in new_file.items() if k not in both}

                    if added:
                        Globals.app.print_info('backup', f'{len(added)} videos have been added to the playlist:')
                        for entry in added:
                            Globals.app.print_info('backup',
                                                   f'{added[entry]["title"]}, {added[entry]["uploader"]}, {entry}')
                        Globals.app.print_info('backup',
                                               '-------------------------------------------------------------------')

                    if deleted:
                        Globals.app.print_info('backup',
                                               f'{len(deleted)} videos have been deleted from the playlist:')
                        for entry in deleted:
                            Globals.app.print_info(
                                'backup', f'{deleted[entry]["title"]}, {deleted[entry]["uploader"]}, {entry}'
                            )
                        Globals.app.print_info('backup',
                                               '-------------------------------------------------------------------')

                    if not added and not deleted:
                        Globals.app.print_info('backup', 'No changes found')

                    # save changes to file
                    changes = {'time': datetime.now().strftime('%Y-%m-%d, %H:%M:%S'), 'added': added,
                               'deleted': deleted}
                    changes_file = []
                    try:
                        with open(f'backups/{info["id"]}_changes.json', 'r') as f:
                            changes_file = json.load(f)
                    except FileNotFoundError as e:
                        Globals.app.print_info('backup', 'No earlier changes found')

                    with open(f'backups/{info["id"]}_changes.json', 'w') as f:
                        changes_file.append(changes)
                        json.dump(changes_file, f)
                        Globals.app.print_info('backup', f'Changes have been saved to {f.name}')

                # save new data to old file
                with open(f'backups/{info["id"]}.json', 'w') as f:
                    json.dump(new_file, f)
                    Globals.app.print_info('backup', f'New playlist data has been backed up to {f.name}')

    Globals.app.reset()

    # reactivate windows sleep mode
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


if __name__ == '__main__':
    Globals.app = App()
    Globals.app.mainloop()
