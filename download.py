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
    # dict of IDs and filenames of videos that are already present in the output folder and where metadata has been set
    already_finished: dict[str, str] = {}
    # list of filenames that are already downloaded but still in the playlist, so they shouldn't be deleted when syncing
    dont_delete: list[str] = []
    start = datetime.now()
    metadata_file: dict[str, dict[str, str]] = {}
    saved_urls: dict[str, dict[str, str]] = {}
    num_threads: int = 100
    metadata_widgets = None
    metadata_names: list[ttk.Widget] = []

    try:
        with open('metadata.json', 'r', encoding='utf-8') as f:
            metadata_file = json.load(f)
        with open('saved_urls.json', 'r') as f:
            saved_urls = json.load(f)
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
                              ttk.Checkbutton(root, command=lambda row=i: self.capitalize(row, 2)),
                              ttk.Checkbutton(root, command=lambda row=i: self.new_swap(row)),
                              ttk.Combobox(root, values=f['title'], width=50),
                              ttk.Checkbutton(root, command=lambda row=i: self.capitalize(row, 5)),

                              ttk.Combobox(root, values=f['album'], width=30),
                              ttk.Combobox(root, values=f['track'], width=5),
                              ttk.Checkbutton(root, command=lambda row=i: self.previous_artist_album(row)),

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
            self.rows[i][13].set(f['comment'][0] if f['comment'] else '')

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
            while not self.rows[first_tick][column].instate(['selected']) and row >= 1:
                first_tick -= 1

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

            current = list(Globals.files.values())[i]
            if self.mode == 'album':
                self.rows[i][6].set(current['album'][0] if current['album'] else '')
                self.rows[i][6]['values'] = current['album']

                self.rows[i][7].set(current['track'][0] if current['track'] else '')
                self.rows[i][7]['values'] = current['track']
            elif self.mode == 'vgm':
                self.rows[i][6].set(l[1].get() + ' OST')
                self.rows[i][6]['values'] = [i + ' OST' for i in l[1]['values']]

                self.rows[i][7].set('')
                self.rows[i][7]['values'] = []

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


# remove characters that are not allowed in filenames (by windows)
def safe_filename(filename: str) -> str:
    for c in ['\\', '/', ':', '?', '"', '*', '<', '>', '|']:
        filename = filename.replace(c, '')
    return filename


# convert number of seconds to string with format minutes:seconds
def sec_to_min(sec: int) -> str:
    return f"{sec // 60}:{'0' if (sec % 60) < 10 else ''}{sec % 60}"


def main():
    class Logger(object):
        def debug(self, msg):
            time = f"[{datetime.now().strftime('%H:%M:%S')}] "
            msg = msg.replace('\r', '')

            error_text['state'] = 'normal'
            if '[download]  ' in msg or '[download] 100.0%' in msg:
                if debug.get() == '1':
                    error_text.delete('end-1l', 'end')
                    error_text.insert('end', '\n' + f'{time}{msg}')
                print(f"\r{time}{msg}", end='', flush=True)
            elif '[download] 100%' in msg:
                if debug.get() == '1':
                    error_text.delete('end-1l', 'end')
                    error_text.insert('end', '\n' + f'{time}{msg}' + '\n')
                print(f"\r{time}{msg}")
            else:
                if debug.get() == '1':
                    error_text.insert('end', f'{time}{msg}' + '\n')
                print(f'{time}{msg}')
            error_text.see('end')
            error_text['state'] = 'disabled'

            Tk.update(root)

        def warning(self, msg):
            print_error('warning', msg)

        def error(self, msg):
            print_error('error', msg)

    def print_error(process: str, msg):
        msg = f"[{datetime.now().strftime('%H:%M:%S')}] [{process}] {msg}"
        error_text['state'] = 'normal'
        error_text.insert('end', msg + '\n')
        error_text.see('end')
        error_text['state'] = 'disabled'
        print(msg)
        Tk.update(root)

    def generate_metadata_choices(metadata: dict[str, Any]) -> dict[str, Union[str, list[str]]]:
        choices = {'id': metadata['id'], 'originaltitle': metadata['title']}

        title_choices: list[str] = []
        artist_choices: list[str] = []
        album_choices: list[str] = []
        track_choices: list[str] = []

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

        if 'artist' in metadata:
            artist = metadata['artist'] if metadata['artist'] else ''
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
        if metadata_mode.get() == 'vgm':
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
        if metadata_mode.get() == 'classical':
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
                text = text.lower()
                if 'major' in text or 'dur' in text:
                    key = key.upper()
                elif 'minor' in text or 'moll' in text:
                    key = key.lower()

                if 'sharp' in text or len(text) > 1 and text[1] == '#':
                    key += 's'
                elif 'flat' in text or len(text) > 1 and (text[1] == 'b' or text[1] == '♭'):
                    key += 'b'

                key_choices.append(key)

            # work choices
            title_lower: str = lower_and_remove_symbols(title)
            for w in [' ' + f.lower().replace('.', '') + ' ' for f in Globals.classical_work_formats]:
                if w in title_lower:
                    words: list[str] = title_lower.split(w)[-1].split()
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
            dict.fromkeys(filter(None, composer_choices if metadata_mode.get() == 'classical' else artist_choices)))
        choices['album'] = list(dict.fromkeys(album_choices))
        choices['track'] = list(dict.fromkeys(track_choices))
        choices['type'] = list(dict.fromkeys(type_choices))
        choices['number'] = list(dict.fromkeys(number_choices))
        choices['key'] = list(dict.fromkeys(key_choices))
        choices['work'] = list(dict.fromkeys(work_choices))
        choices['comment'] = list(dict.fromkeys(comment_choices))

        return choices

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
                print_error('cut', e)

        try:
            id3 = ID3(path)
            id3.add(TPE1(text=data['artist']))
            id3.add(TIT2(text=data['title']))
            id3.add(TPUB(text=id))

            # Album and VGM Metadata
            if metadata_mode.get() == 'album' or metadata_mode.get() == 'vgm':
                id3.add(TALB(text=data['album']))
                id3.add(TRCK(text=str(data['track'])))

            # Genre based on metadata mode
            genres: dict[str, str] = {'vgm': 'VGM', 'classical': 'Klassik'}
            if metadata_mode.get() in genres:
                id3.add(TCON(text=genres[metadata_mode.get()]))

            id3.save()

            if 'cut' not in data:
                os.rename(path, filename)
        except MutagenError as e:
            print_error('mutagen', e)
        except OSError as e:
            print_error('OS', e)

        Globals.metadata_file[id] = {key: data[key] for key in ['artist', 'title', 'album', 'track']}
        if 'cut' in data:
            Globals.metadata_file[id]['cut'] = data['cut']
            send2trash('cut.info')

    def reset():
        # save metadata to file
        with open('metadata.json', 'w') as f:
            json.dump(Globals.metadata_file, f)

        # save saved urls to file
        with open('saved_urls.json', 'w') as f:
            json.dump(Globals.saved_urls, f)

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

        # reset globals
        Globals.folder = ''
        Globals.files = {}
        Globals.already_finished = {}
        Globals.dont_delete = []

        # reset widgets
        disable_widgets([metadata_button])
        if Globals.metadata_widgets:
            Globals.metadata_widgets.reset()
            Globals.metadata_widgets = None
        for w in Globals.metadata_names:
            w.grid_forget()

        enable_widgets(download_widgets)
        url_combobox.set('')
        progress_text.set('')
        output_folder_variable.set('Folder: Default (click to open)')

    # download mode dependent methods
    # download modes that download files (Download, Sync)
    def download():
        # create out folder if it doesn't exist
        try:
            os.mkdir('out')
        except OSError:
            pass

        # don't download if the url entry is empty
        if not url_combobox.get():
            return

        Globals.start = datetime.now()

        # disable download widgets
        disable_widgets(download_widgets)

        # add IDs of already finished files to a list
        Globals.already_finished = {}
        folder = Globals.folder if Globals.folder else 'out'
        for f in os.listdir(folder):
            if f.split('.')[-1] == 'mp3':
                try:
                    id3 = ID3(os.path.join(folder, f))
                    video_id = id3.getall('TPUB')[0].text[0]
                    if video_id:
                        Globals.already_finished[video_id] = f
                except IndexError:
                    print(f'[Debug] {f} has no TPUB-Frame set')

        # prevent windows sleep mode
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)

        # obtain info to decide between video or playlist download
        url = url_combobox.get()
        url = Globals.saved_urls[url]['url'] if url in Globals.saved_urls else url

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
        info = ydl.extract_info(url, process=False)

        # reset if info is empty
        if not info:
            reset()
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
            return

        # playlist download
        if info['webpage_url_basename'] == 'playlist':
            def download_from_playlist(video_id):
                try:
                    ydl.extract_info('https://youtu.be/' + video_id)
                    # Globals.files[video_id]['album'].append(info['title'])
                    # Globals.files[video_id]['track'].append(str(ids.index(video_id) + 1))
                except youtube_dl.DownloadError as e:
                    print_error('multithreading_download', e)
                    video_queue.put(video_id)

            def threading_worker():
                while True:
                    try:
                        id = video_queue.get(block=False)
                        download_from_playlist(id)
                        video_queue.task_done()
                    except queue.Empty:
                        break

            entries = list(info['entries'])
            ids = [e['id'] for e in entries]

            video_queue = queue.Queue()
            for id in ids:
                video_queue.put(id)

            threads = []
            for i in range(Globals.num_threads):
                t = threading.Thread(target=threading_worker)
                t.start()
                threads.append(t)

            playlist_title = info['title']
            playlist_length = len(entries)
            while active_threads := len([t for t in threads if t.is_alive()]):
                queue_length = video_queue.qsize()
                videos_done = playlist_length - queue_length - active_threads

                progress = videos_done / playlist_length * 100

                progress_bar.set(progress)
                progress_text.set(f'Downloading playlist "{playlist_title}" with {active_threads} thread' +
                                  ('s' if active_threads != 1 else '') +
                                  f', {videos_done}/{playlist_length} ({round(progress, 1)}%) finished, '
                                  f'{sec_to_min((datetime.now() - Globals.start).seconds)} elapsed')
                Tk.update(root)
                sleep(0.1)

        # video download
        else:
            ydl_opts['progress_hooks'] = [video_hook]
            ydl = youtube_dl.YoutubeDL(ydl_opts)
            while True:
                try:
                    ydl.extract_info(url)
                    break
                except youtube_dl.DownloadError as e:
                    print_error('download', str(e) + " (Trying again)")
                    continue

        progress_bar.set(0)

        progress_text.set(f"Downloaded {len(Globals.files)} video{'s' if len(Globals.files) != 1 else ''} in "
                          f"{sec_to_min((datetime.now() - Globals.start).seconds)}")

        # delete all files from the destination folder that are not in the dont_delete list
        # (which means they were removed from the playlist) (only in sync mode)
        if Globals.already_finished and Globals.folder and download_mode.get() == 'sync':
            for f in Globals.already_finished.values():
                if f not in Globals.dont_delete:
                    try:
                        if sync_ask_delete.get() == '0' or messagebox.askyesno(title='Delete file?', icon='question',
                                                                               message=f'The video connected to "{f}" '
                                                                                       f'is not in the playlist '
                                                                                       f'anymore. Do you want to '
                                                                                       f'delete the file?'):
                            os.remove(os.path.join(Globals.folder, f))
                            print_error('sync', f'Deleting {f}')
                    except OSError as e:
                        print_error('sync', e)

        # reactivate windows sleep mode
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)

        # reset if the files dict is empty (no metadata to be set)
        if not Globals.files:
            reset()
            return

        Globals.metadata_widgets = MetadataSelection(metadata_frame, list(Globals.files.values()), metadata_mode.get())
        update_metadata_mode()

        enable_widgets([metadata_button])

    # download modes that download metadata (Calculate length, Download metadata, Backup playlist)
    def download_metadata():
        debug.set('1')

        disable_widgets(download_widgets)

        # prevent windows sleep mode
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)

        mode = download_mode.get()
        url = url_combobox.get()
        ydl_opts = {
            'ignoreerrors': True,
            'logger': Logger(),
            'default_search': 'ytsearch'
        }

        ydl = youtube_dl.YoutubeDL(ydl_opts)
        info = ydl.extract_info(Globals.saved_urls[url]['url'] if url in Globals.saved_urls else url, download=False,
                                process=mode == 'metadata')

        if info:
            # mode dependent actions
            match mode:
                case 'metadata':
                    try:
                        with open(f'out/{safe_filename(info["title"])}.json', 'w') as f:
                            json.dump(info, f)
                    except OSError as e:
                        print_error('OS', e)
                    except Exception as e:
                        print_error('download_metadata', e)

                case 'length':
                    def convert_time(sec):
                        h = int(sec // 3600)
                        min = int(sec % 3600 // 60)
                        seconds = int(sec % 60)
                        return f'{h}:{"0" if min < 10 else ""}{min}:{"0" if seconds < 10 else ""}{seconds}'

                    try:
                        playlist = info['webpage_url_basename'] == 'playlist'
                        duration = sum([i['duration'] for i in list(info['entries'])]) if playlist else info['duration']

                        print_error('length',
                                    f'Length of {"playlist" if playlist else "video"} "{info["title"]}": '
                                    f'{convert_time(duration)}')
                    except KeyError as e:
                        print_error('length', e)

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
                        print_error('backup', 'No earlier backup found')

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
                            print_error('backup', f'{len(added)} videos have been added to the playlist:')
                            for entry in added:
                                print_error('backup', f'{added[entry]["title"]}, {added[entry]["uploader"]}, {entry}')
                            print_error('backup', '-------------------------------------------------------------------')

                        if deleted:
                            print_error('backup', f'{len(deleted)} videos have been deleted from the playlist:')
                            for entry in deleted:
                                print_error(
                                    'backup', f'{deleted[entry]["title"]}, {deleted[entry]["uploader"]}, {entry}'
                                )
                            print_error('backup', '-------------------------------------------------------------------')

                        if not added and not deleted:
                            print_error('backup', 'No changes found')

                        # save changes to file
                        changes = {'time': datetime.now().strftime('%Y-%m-%d, %H:%M:%S'), 'added': added,
                                   'deleted': deleted}
                        changes_file = []
                        try:
                            with open(f'backups/{info["id"]}_changes.json', 'r') as f:
                                changes_file = json.load(f)
                        except FileNotFoundError as e:
                            print_error('backup', 'No earlier changes found')

                        with open(f'backups/{info["id"]}_changes.json', 'w') as f:
                            changes_file.append(changes)
                            json.dump(changes_file, f)
                            print_error('backup', f'Changes have been saved to {f.name}')

                    # save new data to old file
                    with open(f'backups/{info["id"]}.json', 'w') as f:
                        json.dump(new_file, f)
                        print_error('backup', f'New playlist data has been backed up to {f.name}')

        reset()

        # reactivate windows sleep mode
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)

    # methods for getting information about videos/playlists from youtube_dl while downloading to update the GUI
    # video downloading,    call from hook:          originaltitle, downloaded_bytes, total_bytes, eta
    # video downloading,    call from get_info_dict: title, playlist (None), playlist_index (None)
    # playlist downloading, call from hook:          originaltitle, playlist, playlist_index, playlist_length, downloaded_bytes, total_bytes, eta
    # playlist downloading, call from get_info_dict: title, playlist, playlist_index, n_entries
    def update_progress_video(video_info, download_info):
        try:
            title = video_info['originaltitle'] if 'originaltitle' in video_info else video_info['title']

            progress = download_info['downloaded_bytes'] / download_info['total_bytes'] * 100
            progress_content = (
                f"Downloading video {title}, {round(progress)}% finished, {sec_to_min(download_info['eta'])} left"
            )

            progress_bar.set(progress)
            progress_text.set(progress_content)
        except Exception as e:
            print_error("GUI updater", e)
            progress_text.set('Downloading...')

        Tk.update(root)

    def video_hook(d):
        file = list(Globals.files.values())[-1]

        match d['status']:
            case 'downloading':
                update_progress_video(file, d)
            case 'finished':
                progress_text.set('Converting...')

        Tk.update(root)

    def get_info_dict(info_dict):
        # don't download and don't add to files dict if file is already present and metadata has already been set,
        # don't delete that file when syncing
        if info_dict['id'] in Globals.already_finished:
            Globals.dont_delete.append(Globals.already_finished[info_dict['id']])
            print_error('download', f"{info_dict['id']}: File with metadata already present")
            return f"{info_dict['id']}: File with metadata already present"

        Globals.files[info_dict['id']] = generate_metadata_choices(info_dict)

        # don't download if file is already present
        if os.path.isfile(os.path.join('out', info_dict['id'] + '.mp3')):
            print_error('download', f"{info_dict['id']}: File already present")
            return f"{info_dict['id']}: File already present"

    # GUI methods
    def enable_widgets(widgets: list) -> None:
        for w in widgets:
            w.state(['!disabled'])

    def disable_widgets(widgets: list) -> None:
        for w in widgets:
            w.state(['disabled'])

    def apply_all_metadata():
        for i, file in enumerate(Globals.metadata_widgets.data):
            file['artist'] = Globals.metadata_widgets.rows[i][1].get()
            file['title'] = Globals.metadata_widgets.rows[i][4].get()

            if metadata_mode.get() == 'album' or metadata_mode.get() == 'vgm':
                file['album'] = Globals.metadata_widgets.rows[i][6].get()
                file['track'] = Globals.metadata_widgets.rows[i][7].get()
            else:
                file['album'] = ''
                file['track'] = ''

            if metadata_mode.get() == 'classical' and Globals.metadata_widgets.rows[i][14].get().strip():
                file['cut'] = Globals.metadata_widgets.rows[i][14].get()

            apply_metadata(file['id'], file)

        reset()

    def save_url():
        url = simpledialog.askstring(title='Save URL',
                                     prompt='Input the name under which to save the URL and settings:')
        if url:
            Globals.saved_urls[url] = {'url': url_combobox.get(), 'folder': Globals.folder,
                                       'metadata_mode': metadata_mode.get()}
        url_combobox['values'] = list(Globals.saved_urls.keys())

    def select_output_folder():
        Globals.folder = filedialog.askdirectory()
        output_folder_variable.set('Folder: ' + (Globals.folder if Globals.folder else 'Default') + ' (click to open)')

    def open_output_folder(event):
        if Globals.folder:
            folder = Globals.folder.replace('/', "\\")
            subprocess.run(f'explorer.exe "{folder}"')
        else:
            subprocess.run('explorer.exe out')

    # menu click methods
    def update_download_mode():
        for w in download_mode_widgets:
            w.grid_forget()

        match download_mode.get():
            case 'download':
                output_folder_button['text'] = 'Select output folder'
                download_button['text'] = 'Download'
                download_button['command'] = download
                output_folder_button.grid(row=1, column=0, pady=(5, 0), sticky='W')
                output_folder_label.grid(row=1, column=width // 6, columnspan=width - width // 6, sticky='W')
            case 'sync':
                output_folder_button['text'] = 'Select folder to sync with'
                sync_ask_delete_checkbutton.grid(row=11, column=0, pady=(5, 0), sticky='W')

                download_button['text'] = 'Download and Sync'
                download_button['command'] = download
            case 'length':
                download_button['text'] = 'Calculate length'
                download_button['command'] = download_metadata
            case 'metadata':
                download_button['text'] = 'Download Metadata'
                download_button['command'] = download_metadata
            case 'backup':
                download_button['text'] = 'Backup Playlist/Search for Changes'
                download_button['command'] = download_metadata

    def update_metadata_mode():
        if Globals.metadata_widgets:
            for i, name in enumerate(Globals.metadata_names):
                name.grid_forget()
                if i < 6 or (metadata_mode.get() == 'album' or metadata_mode.get() == 'vgm') \
                        and i < 9 or metadata_mode.get() == 'classical' and i >= 9:
                    name.grid(row=0, column=i)
                    name.bind('<MouseWheel>', scroll)

            Globals.metadata_widgets.mode = metadata_mode.get()
            Globals.metadata_widgets.grid()

            for l in Globals.metadata_widgets.rows:
                for w in l:
                    w.bind('<MouseWheel>', scroll)

    # event methods
    # track changes of comboboxes to update other comboboxes
    def url_combobox_write(*args):
        if (url := url_combobox.get()) in Globals.saved_urls:
            Globals.folder = Globals.saved_urls[url]['folder']
            output_folder_variable.set(
                'Folder: ' + (Globals.folder if Globals.folder else 'Default') + ' (click to open)')

            metadata_mode.set(Globals.saved_urls[url]['metadata_mode'])
            update_metadata_mode()

    # track change of window size
    def size_changed(event):
        try:
            error_text['height'] = (root.winfo_height() - download_frame.winfo_height() -
                                    metadata_labelframe.winfo_height() - 80) // 16
        except NameError:
            pass

    def scroll(event):
        metadata_canvas.yview_scroll(int(-1 * (event.delta / 40)), UNITS)
        return 'break'

    # track exit of program
    def on_exit():
        reset()
        root.destroy()

    root = Tk()
    root.title('YouTube to MP3 Converter')
    root.geometry('800x720')
    root.option_add('*tearOff', FALSE)
    root.bind('<Configure>', size_changed)
    root.protocol("WM_DELETE_WINDOW", on_exit)

    download_frame = ttk.Labelframe(root, padding=(3, 10, 12, 12), borderwidth=5, relief='ridge', text='Download')

    metadata_labelframe = ttk.Labelframe(root, padding=(3, 10, 12, 12), borderwidth=5, relief='ridge', text='Metadata')

    error_frame = ttk.Labelframe(root, padding=(3, 10, 12, 12), borderwidth=5, relief='ridge', text='Info and Errors')

    # menu variables
    download_mode = StringVar()
    download_mode.set('download')
    metadata_mode = StringVar()
    metadata_mode.set('normal')
    debug = StringVar()
    debug.set('0')

    # widget variables
    url_variable = StringVar()
    artist_variable = StringVar()
    artist_variable.set('Select the artist:')
    output_folder_variable = StringVar()
    output_folder_variable.set('Folder: Default (click to open)')
    sync_ask_delete = StringVar()
    sync_ask_delete.set('1')
    progress_text = StringVar()
    progress_bar = DoubleVar()

    # menu
    menubar = Menu(root)
    root['menu'] = menubar

    menu_download_mode = Menu(menubar)
    menubar.add_cascade(menu=menu_download_mode, label='Download Mode')
    menu_download_mode.add_radiobutton(label='Download', variable=download_mode, value='download',
                                       command=update_download_mode)
    menu_download_mode.add_radiobutton(label='Sync with Folder', variable=download_mode, value='sync',
                                       command=update_download_mode)
    menu_download_mode.add_radiobutton(label='Calculate length of Playlist', variable=download_mode, value='length',
                                       command=update_download_mode)
    menu_download_mode.add_radiobutton(label='Download metadata', variable=download_mode, value='metadata',
                                       command=update_download_mode)
    menu_download_mode.add_radiobutton(label='Backup Playlist/Search for Changes', variable=download_mode,
                                       value='backup',
                                       command=update_download_mode)

    menu_metadata_mode = Menu(menubar)
    menubar.add_cascade(menu=menu_metadata_mode, label='Metadata Mode')
    menu_metadata_mode.add_radiobutton(label='Normal', variable=metadata_mode, value='normal',
                                       command=update_metadata_mode)
    menu_metadata_mode.add_radiobutton(label='Album', variable=metadata_mode, value='album',
                                       command=update_metadata_mode)
    menu_metadata_mode.add_radiobutton(label='VGM', variable=metadata_mode, value='vgm', command=update_metadata_mode)
    menu_metadata_mode.add_radiobutton(label='Classical', variable=metadata_mode, value='classical',
                                       command=update_metadata_mode)

    menu_debug = Menu(menubar)
    menubar.add_cascade(menu=menu_debug, label='Debug')
    menu_debug.add_checkbutton(label='Show debug messages', variable=debug, onvalue='1', offvalue='0')
    menu_debug.add_command(label='Reset', command=reset)

    # widgets
    # download widgets
    url_label = ttk.Label(download_frame, text='Input video/playlist URL, search query or saved URL name:')
    url_combobox = ttk.Combobox(download_frame, values=list(Globals.saved_urls.keys()), textvariable=url_variable)
    save_url_button = ttk.Button(download_frame, text='Save...', command=save_url)
    output_folder_label = ttk.Label(download_frame, textvariable=output_folder_variable)
    output_folder_button = ttk.Button(download_frame, text='Select output folder...', command=select_output_folder)
    download_button = ttk.Button(download_frame, text='Download',
                                 command=lambda: threading.Thread(target=download).start())
    sync_ask_delete_checkbutton = ttk.Checkbutton(download_frame, text='Ask before deleting files',
                                                  variable=sync_ask_delete)
    progress_label = ttk.Label(download_frame, text='', textvariable=progress_text)
    download_progress = ttk.Progressbar(download_frame, orient=HORIZONTAL, mode='determinate', variable=progress_bar)

    # download widgets that get enabled/disabled
    download_widgets = [url_combobox, save_url_button, output_folder_button, download_button]

    # download mode dependent widgets
    download_mode_widgets = [sync_ask_delete_checkbutton]

    # metadata widgets
    metadata_canvas = Canvas(metadata_labelframe)
    metadata_scrollbar = ttk.Scrollbar(metadata_labelframe, orient=VERTICAL, command=metadata_canvas.yview)
    metadata_frame = ttk.Frame(metadata_canvas)

    metadata_canvas.configure(yscrollcommand=metadata_scrollbar.set)
    metadata_canvas.create_window((0, 0), window=metadata_frame, anchor="nw")

    Globals.metadata_names = [ttk.Label(metadata_frame, text='Video title'),
                              ttk.Label(metadata_frame, text='Artist'),
                              ttk.Label(metadata_frame, text=''),
                              ttk.Label(metadata_frame, text='Swap'),
                              ttk.Label(metadata_frame, text='Title'),
                              ttk.Label(metadata_frame, text=''),

                              ttk.Label(metadata_frame, text='Album'),
                              ttk.Label(metadata_frame, text='Track'),
                              ttk.Label(metadata_frame, text='Previous'),

                              ttk.Label(metadata_frame, text='Type'),
                              ttk.Label(metadata_frame, text='Number'),
                              ttk.Label(metadata_frame, text='Key'),
                              ttk.Label(metadata_frame, text='Work'),
                              ttk.Label(metadata_frame, text='Comment'),
                              ttk.Label(metadata_frame, text='Cut')
                              ]

    metadata_button = ttk.Button(metadata_labelframe, text='Apply metadata', command=apply_all_metadata,
                                 state='disabled')

    # error message widgets
    error_text = ScrolledText(error_frame, wrap=tkinter.WORD, height=10, state='disabled')

    # widget events
    url_variable.trace_add('write', url_combobox_write)
    output_folder_label.bind('<Button-1>', open_output_folder)

    metadata_canvas.bind('<MouseWheel>', scroll)
    metadata_frame.bind('<Configure>', lambda e: metadata_canvas.configure(scrollregion=metadata_canvas.bbox("all")))

    # grid (rows: 0-9 before mode dependent widgets, 10-19 mode dependent widgets, 20-29 after mode dependent widgets)
    width = 6  # number of columns

    download_frame.grid(row=0, column=0, sticky='NEW', padx=5, pady=5)
    url_label.grid(row=0, column=0, columnspan=width // 6, sticky='W')
    url_combobox.grid(row=0, column=width // 6, columnspan=4, sticky='EW')
    save_url_button.grid(row=0, column=width - width // 6, columnspan=width // 6, padx=(5, 0), sticky='W')
    output_folder_button.grid(row=1, column=0, pady=(5, 0), sticky='W')
    output_folder_label.grid(row=1, column=width // 6, columnspan=width - width // 6, sticky='W')
    download_button.grid(row=20, column=width // 6, pady=(5, 0), sticky='W')
    download_progress.grid(row=21, column=0, columnspan=width, pady=5, sticky='EW')
    progress_label.grid(row=22, column=0, columnspan=width)

    metadata_labelframe.grid(row=1, column=0, sticky='NEW', padx=5, pady=5)
    metadata_canvas.pack(side=LEFT, expand=True, fill=X)
    metadata_scrollbar.pack(side=RIGHT, fill=Y)
    metadata_button.pack(before=metadata_canvas, side=BOTTOM, anchor='w')

    error_frame.grid(row=2, column=0, sticky='NEW', padx=5, pady=5)
    error_text.grid(row=0, column=0, columnspan=width, sticky='EW', pady=(5, 0))

    url_combobox.focus()

    root.columnconfigure(0, weight=1)

    for f in [download_frame, metadata_labelframe, error_frame]:
        for i in range(6):
            f.columnconfigure(i, weight=1)

    root.mainloop()


if __name__ == '__main__':
    main()
