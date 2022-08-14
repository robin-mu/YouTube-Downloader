import ctypes  # prevent sleep mode when downloading
import json
import os
import shutil  # moving files between drives when syncing
import subprocess
import tkinter
import webbrowser
from datetime import datetime
from pprint import pprint
from tkinter import *
from tkinter import ttk, filedialog, messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText
from typing import Any
from pydub import AudioSegment

import youtube_dl
from mutagen import MutagenError
from mutagen.id3 import ID3, TIT2, TPE1, TPUB, TALB, TRCK, TCON
from send2trash import send2trash

# change current working directory to script location
os.chdir(os.path.dirname(os.path.realpath(__file__)))


class Globals:
    folder: str = ''  # folder to sync with
    files: list[dict[str, Any]] = []
    current_file: dict[str, Any] = {}
    # dict of IDs and filenames of videos that are already present in the output folder and where metadata has been
    # set
    already_finished: dict[str, str] = {}
    # list of filenames that are already downloaded but still in the playlist, so they shouldn't be deleted when
    # syncing
    dont_delete: list[str] = []
    start = datetime.now()
    metadata_file: dict[str, dict[str, str]] = {}
    saved_urls: dict[str, dict[str, str]] = {}

    try:
        with open('metadata.json', 'r') as f:
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
    classical_work_formats: list[str] = list(dict.fromkeys(['Op.'] + [f for f in
                                                                      classical_work_format_special.values()]))
    classical_composers: list[str] = classical_work_format_opus + \
                                     [item for item in classical_work_format_special.keys()] + \
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

    def generate_metadata_choices(metadata: dict[str, Any]) -> dict[str, Any]:
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
            while '(' in text and ')' in text:
                split: list[str] = text.split('(', 1)
                text = split[0].strip() + ' ' + \
                       (split[1].split(')', 1)[1].strip() if ')' in split[1] else split[1].strip())
            while '[' in text and ']' in text:
                split: list[str] = text.split('[', 1)
                text = split[0].strip() + ' ' + \
                       (split[1].split(']', 1)[1].strip() if ']' in split[1] else split[1].strip())
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
            choices['playlist'] = metadata['playlist']
            album_choices.append(metadata['playlist'])
        if 'playlist_index' in metadata and metadata['playlist_index']:
            choices['playlist_index'] = metadata['playlist_index']
            track_choices.append(metadata['playlist_index'])
        if 'n_entries' in metadata and metadata['n_entries']:
            choices['playlist_length'] = metadata['n_entries']

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

    def update_combobox(from_start: bool):
        # start at 0 if True / next video if False
        if from_start:
            index = 0
        else:
            index = Globals.files.index(Globals.current_file) + 1

        # If 'Apply metadata from json' checkbutton is checked: check if ID at current index is in the loaded metadata
        # and apply it
        while index < len(Globals.files) and Globals.files[index]['id'] in Globals.metadata_file and \
                metadata_file_variable.get() == '1':
            id = Globals.files[index]['id']
            data = Globals.metadata_file[id]
            apply_metadata(id, data)
            index += 1

        # reset if end of playlist is reached
        if index < len(Globals.files):
            Globals.current_file = Globals.files[index]
            file = Globals.current_file

            video_text = f"Select Metadata for: \"{file['originaltitle']}\""
            if 'playlist_index' in file and 'playlist_length' in file:
                video_text += f" ({file['playlist_index']}/{file['playlist_length']})"
            select_metadata_variable.set(video_text)

            # save previous artist and album before they get changed
            if metadata_mode.get() == 'vgm' or metadata_mode.get() == 'album':
                previous_artist = artist_combobox.get()
                previous_album = album_combobox.get()

            if swap_variable.get() == '0':
                artist_combobox['values'] = file['artist']
                title_combobox['values'] = file['title']
                artist_combobox.set(file['artist'][0])
                title_combobox.set(file['title'][0])
            else:
                artist_combobox['values'] = file['title']
                title_combobox['values'] = file['artist']
                artist_combobox.set(file['title'][0])
                title_combobox.set(file['artist'][0])

            if metadata_mode.get() == 'vgm' or metadata_mode.get() == 'album':
                # Album mode
                if metadata_mode.get() == 'album':
                    if file['album']:
                        album_combobox.set(file['album'][0])
                    album_combobox['values'] = file['album']
                    if file['track']:
                        track_combobox.set(file['track'][0])
                    track_combobox['values'] = file['track']

                # VGM mode
                if metadata_mode.get() == 'vgm':
                    album_combobox.set(artist_combobox.get() + ' OST')
                    album_combobox['values'] = [i + ' OST' for i in artist_combobox['values']]

                    track_combobox.set('')
                    track_combobox['values'] = []

                # apply previous artist and album
                if previous_artist:
                    if keep_artist_variable.get() == '1':
                        artist_combobox.set(previous_artist)
                    artist_combobox['values'] += (previous_artist,)

                if previous_album:
                    if keep_artist_variable.get() == '1':
                        album_combobox.set(previous_album)
                    album_combobox['values'] += (previous_album,)

            # Classical mode
            if metadata_mode.get() == 'classical':
                classical_type_combobox['values'] = file['type']
                classical_type_combobox.set(file['type'][0] if file['type'] else '')
                classical_number_combobox['values'] = file['number']
                classical_number_combobox.set(file['number'][0] if file['number'] else '')
                classical_key_combobox['values'] = file['key']
                classical_key_combobox.set(file['key'][0] if file['key'] else '')
                classical_work_combobox['values'] = file['work']
                classical_work_combobox.set(file['work'][0] if file['work'] else '')

                classical_comment_combobox['values'] = file['comment']
                classical_comment_combobox.set('')
                classical_cut_entry.delete(0, 'end')
                if file['id'] in Globals.metadata_file and 'cut' in Globals.metadata_file[file['id']]:
                    classical_cut_entry.insert(0, Globals.metadata_file[file['id']]['cut'])

                if file['file']:
                    title_combobox.set(file['title'][0])
        else:
            reset()

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
                    for cut in data['cut'].split('-'):
                        split_space: list[str] = cut.split(' ')  # a) ['3+5', '1:30+4'] b) ['1:40', '2:30+5']

                        if '+' in split_space[0]:  # true for a), false for b)
                            split_plus: list[str] = split_space[0].split('+')  # ['3', '5']
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
                    subprocess.run(f'ffmpeg.exe -filter_complex'
                                   f' anullsrc=sample_rate={AudioSegment.from_mp3(path).frame_rate} -t {highest} s.mp3')

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

                if metadata_mode.get() == 'vgm':
                    id3.add(TCON(text='VGM'))

            if metadata_mode.get() == 'classical':
                id3.add(TCON(text='Klassik'))
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
        Globals.files = []
        Globals.current_file = {}
        Globals.already_finished = {}
        Globals.dont_delete = []

        # reset comboboxes
        for c in [artist_combobox, title_combobox, album_combobox, track_combobox, classical_type_combobox,
                  classical_number_combobox, classical_key_combobox, classical_work_combobox,
                  classical_comment_combobox]:
            c.set('')
            c['values'] = []

        # reset widgets
        disable_widgets(metadata_widgets)
        enable_widgets(download_widgets)
        url_combobox.set('')
        progress_text.set('')
        video.set('')
        select_metadata_variable.set('')
        output_folder_variable.set('Folder: Default (click to open)')

        # VGM mode
        keep_artist_variable.set('0')

        # Classical mode
        classical_cut_entry.delete(0, 'end')

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
                    print(f'{f} has no TPUB-Frame set')

        # prevent windows sleep mode
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)

        url = url_combobox.get()
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
        info = ydl.extract_info(Globals.saved_urls[url]['url'] if url in Globals.saved_urls else url)

        # reset if info is empty
        if not info:
            reset()
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
            return

        video.set('')

        # check which videos haven't been downloaded when downloading a playlist
        if info['webpage_url_basename'] == 'playlist':
            def get_not_downloaded(info) -> str:
                results = ''

                for entry in info['entries']:
                    if entry and 'id' in entry and entry['id']:
                        if not os.path.isfile(os.path.join('out', entry['id'] + '.mp3')) and \
                                not entry['id'] in Globals.already_finished:
                            results += str(entry["playlist_index"]) + ','

                return results.rstrip(',')

            not_downloaded = get_not_downloaded(info)

            # try to download all not downloaded videos again
            if not_downloaded:
                print_error('download',
                            f'{(len(not_downloaded) + 1) // 2} videos have not been downloaded. Trying again...')
                ydl_opts['playlist_items'] = not_downloaded
                ydl = youtube_dl.YoutubeDL(ydl_opts)
                ydl.download([Globals.saved_urls[url] if url in Globals.saved_urls else url])

            not_downloaded = get_not_downloaded(info)

            # print IDs of all videos that still couldn't be downloaded
            if not_downloaded:
                print_error('download',
                            f'{(len(not_downloaded) + 1) // 2} videos could not be downloaded. '
                            f'Their indexes are: {not_downloaded}')

        progress_bar.set(0)

        time = (datetime.now() - Globals.start).seconds
        progress_text.set(f"Downloaded {len(Globals.files)} video{'s' if len(Globals.files) != 1 else ''} in "
                          f"{sec_to_min(time)}")
        video.set('')

        # delete all files from the destination folder that are not in the dont_delete list
        # (which means they were removed from the playlist) (only in sync mode)
        if Globals.already_finished and Globals.folder and download_mode.get() == 'sync':
            for f in Globals.already_finished.values():
                if f not in Globals.dont_delete:
                    try:
                        if sync_ask_delete.get() == '0':
                            os.remove(os.path.join(Globals.folder, f))
                            print_error('sync', f'Deleting {f}')
                        elif messagebox.askyesno(title='Delete file?', icon='question',
                                                 message=f'The video connected to "{f}" is not in the playlist '
                                                         f'anymore. Do you want to delete the file?'):
                            os.remove(os.path.join(Globals.folder, f))
                            print_error('sync', f'Deleting {f}')
                    except OSError as e:
                        print_error('sync', e)

        # reactivate windows sleep mode
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)

        # reset if the files list is empty (no metadata to be set)
        if not Globals.files:
            reset()
            return

        update_combobox(True)

        # start metadata selection if not all metadata has been already set (reset in update_combobox hasn't been
        # executed yet)
        if Globals.current_file:
            enable_widgets(metadata_widgets)

    # download modes that download metadata (Calculate length, Download metadata, Backup playlist)
    def download_metadata():
        debug.set('1')

        disable_widgets(download_widgets)

        # prevent windows sleep mode
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)

        url = url_combobox.get()
        ydl_opts = {
            'ignoreerrors': True,
            'logger': Logger(),
            'default_search': 'ytsearch'
        }

        ydl = youtube_dl.YoutubeDL(ydl_opts)
        info = ydl.extract_info(Globals.saved_urls[url] if url in Globals.saved_urls else url,
                                download=False)  # ie_key='Youtube' could be faster

        # mode dependent actions
        mode = download_mode.get()
        if mode == 'metadata':
            try:
                with open(f'out/{safe_filename(info["title"])}.json', 'w') as f:
                    json.dump(info, f)
            except OSError as e:
                print_error('OS', e)
            except Exception as e:
                print_error('download_metadata', e)

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

            print_error('length',
                        f'Length of {"playlist" if playlist else "video"} "{info["title"]}": {convert_time(duration)}')

        elif mode == 'backup':
            # make backups folder if it doesn't exist
            try:
                os.mkdir('backups')
            except OSError:
                pass

            # load old file if the playlist has been backed up before
            old_file = {}
            try:
                with open(f'backups/{info["id"]}.json', 'r') as f:
                    old_file = json.load(f)
            except Exception:
                print_error('backup', 'No earlier backup found')

            # extract title, uploader and description from info
            new_file: dict[str, Any] = {'title': info['title']}
            if info['webpage_url_basename'] == 'playlist':
                for entry in info['entries']:
                    if entry:
                        new_file[entry['id']] = {'title': entry['title'], 'uploader': entry['uploader'],
                                                 'description': entry['description']}
            # compare both files if the playlist has been backed up before
            if old_file:
                both = []
                for entry in old_file:
                    if entry in new_file:
                        both.append(entry)

                deleted = {k: v for (k, v) in old_file.items() if k not in both}
                added = {k: v for (k, v) in new_file.items() if k not in both}

                if added:
                    print_error('backup', f'{len(added)} videos have been added to the playlist:')
                    for entry in added:
                        print_error('backup', f'{added[entry]["title"]}, {added[entry]["uploader"]}, {entry}')
                    print_error('backup', '------------------------------')

                if deleted:
                    print_error('backup', f'{len(deleted)} videos have been deleted from the playlist:')
                    for entry in deleted:
                        print_error('backup', f'{deleted[entry]["title"]}, {deleted[entry]["uploader"]}, {entry}')
                    print_error('backup', '------------------------------')

                if not added and not deleted:
                    print_error('backup', 'No changes found')

                # save changes to file
                changes = {'time': datetime.now().strftime('%Y-%m-%d, %H:%M:%S'), 'added': added, 'deleted': deleted}
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

        reset()

        # reactivate windows sleep mode
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)

    # methods for getting information about videos/playlists from youtube_dl while downloading to update the GUI
    # video downloading,    call from hook:          originaltitle, downloaded_bytes, total_bytes, eta
    # video downloading,    call from get_info_dict: title, playlist (None), playlist_index (None)
    # playlist downloading, call from hook:          originaltitle, playlist, playlist_index, playlist_length, downloaded_bytes, total_bytes, eta
    # playlist downloading, call from get_info_dict: title, playlist, playlist_index, n_entries
    def update_progress(video_info, download_info):
        try:
            title = video_info['originaltitle'] if 'originaltitle' in video_info else video_info['title']

            # playlist download
            if 'playlist' in video_info and video_info['playlist']:
                length = video_info['n_entries'] if 'n_entries' in video_info else video_info['playlist_length']

                time = sec_to_min((datetime.now() - Globals.start).seconds)
                progress = ((video_info['playlist_index'] - 1) / length
                            + ((download_info['downloaded_bytes'] / download_info['total_bytes'] / length)
                               if download_info else 0)) * 100

                progress_content = (
                        f"Downloading playlist \"{video_info['playlist']}\"" +
                        (f", {video_info['playlist_index']}/{length} ({round(progress, 1)}% finished, "
                         if progress <= 100 else ' (') +
                        f"{time} elapsed)"
                )

                video_content = (
                        f"Current video: {title}" +
                        (f", {download_info['downloaded_bytes'] * 100 // download_info['total_bytes']}% "
                         f"finished, {sec_to_min(download_info['eta'])} left" if download_info else '')
                )

            # video download
            else:
                progress = (download_info['downloaded_bytes'] / download_info['total_bytes'] * 100) \
                    if download_info else 0
                progress_content = (
                        f"Downloading: {title}" +
                        (f", {round(progress)}% finished, {sec_to_min(download_info['eta'])} left"
                         if download_info else '')
                )
                video_content = ''

            progress_bar.set(progress)
            progress_text.set(progress_content)
            video.set(video_content)
        except Exception as e:
            print_error("GUI updater", e)
            progress_text.set('Downloading...')
            video.set('')

        Tk.update(root)

    def hook(d):
        # get current file
        file = Globals.files[-1]

        if d['status'] == 'downloading':
            update_progress(file, d)
        if d['status'] == 'finished':
            if 'playlist' in file:
                video.set('Converting...')
            else:
                progress_text.set('Converting...')
        Tk.update(root)

    def get_info_dict(info_dict):
        # don't download and don't add to file list if file is already present and metadata has already been set,
        # don't delete that file when syncing
        if info_dict['id'] in Globals.already_finished:
            Globals.dont_delete.append(Globals.already_finished[info_dict['id']])
            print_error('download', f"{info_dict['id']}: File with metadata already present")

            update_progress(info_dict, [])

            return f"{info_dict['id']}: File with metadata already present"

        file: dict[str, Any] = generate_metadata_choices(info_dict)

        # avoid duplicate entries with same ID
        for f in Globals.files:
            if f['id'] == info_dict['id']:
                Globals.files.remove(f)

        Globals.files.append(file)

        # don't download if file is already present
        if os.path.isfile(os.path.join('out', info_dict['id'] + '.mp3')):
            print_error('download', f"{info_dict['id']}: File already present")
            update_progress(info_dict, [])
            return f"{info_dict['id']}: File already present"

    # GUI methods
    def enable_widgets(widgets: list) -> None:
        for w in widgets:
            w.state(['!disabled'])

    def disable_widgets(widgets: list) -> None:
        for w in widgets:
            w.state(['disabled'])

    # button click methods
    def apply_metadata_once():
        file = Globals.current_file
        file['artist'] = artist_combobox.get()
        file['title'] = title_combobox.get()
        file['album'] = album_combobox.get()
        file['track'] = track_combobox.get()
        if metadata_mode.get() == 'classical' and classical_cut_entry.get().strip():
            file['cut'] = classical_cut_entry.get()
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
        if metadata_file_variable.get() == '1' and Globals.current_file and \
                Globals.current_file['id'] in Globals.metadata_file:
            id = Globals.current_file['id']
            data = Globals.metadata_file[id]
            apply_metadata(id, data)
            update_combobox(False)

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

    def open_url(event):
        if Globals.current_file:
            webbrowser.open_new('https://youtu.be/' + Globals.current_file['id'])

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

    # menu click methods
    def update_download_mode():
        for w in download_mode_widgets:
            w.grid_forget()

        mode = download_mode.get()
        if mode == 'download':
            output_folder_button['text'] = 'Select output folder'
            download_button['text'] = 'Download'
            download_button['command'] = download
            output_folder_button.grid(row=1, column=0, pady=(5, 0), sticky='W')
            output_folder_label.grid(row=1, column=width // 6, columnspan=width - width // 6, sticky='W')
        elif mode == 'sync':
            output_folder_button['text'] = 'Select folder to sync with'
            sync_ask_delete_checkbutton.grid(row=11, column=0, pady=(5, 0), sticky='W')

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
        for w in metadata_mode_widgets:
            w.grid_forget()

        mode: str = metadata_mode.get()

        artist_variable.set('Select the artist:')
        if mode == 'album' or mode == 'vgm':
            album_label.grid(row=10, column=0, columnspan=width // 6, sticky='W', pady=2)
            album_combobox.grid(row=10, column=width // 6, columnspan=4, sticky='EW')
            track_label.grid(row=11, column=0, columnspan=width // 6, sticky='W', pady=2)
            track_combobox.grid(row=11, column=width // 6, columnspan=4, sticky='EW')
            keep_artist_checkbutton.grid(row=12, column=0, sticky='W')

            if Globals.current_file:
                file = Globals.current_file
                if mode == 'album':
                    album_combobox.set(file['album'][0])
                    album_combobox['values'] = file['album']
                    track_combobox.set(file['track'][0])
                    track_combobox['values'] = file['track']
                elif mode == 'vgm':
                    album_combobox.set(artist_combobox.get() + ' OST')
                    album_combobox['values'] = [i + ' OST' for i in artist_combobox['values']]

        elif mode == 'classical':
            artist_variable.set('Select the composer:')

            classical_type_label.grid(row=10, column=0, columnspan=width // 6, sticky='W', pady=2)
            classical_type_combobox.grid(row=10, column=width // 6, columnspan=4, sticky='EW')
            classical_number_label.grid(row=11, column=0, columnspan=width // 6, sticky='W', pady=2)
            classical_number_combobox.grid(row=11, column=width // 6, columnspan=4, sticky='EW')
            classical_key_label.grid(row=12, column=0, columnspan=width // 6, sticky='W', pady=2)
            classical_key_combobox.grid(row=12, column=width // 6, columnspan=4, sticky='EW')
            classical_work_label.grid(row=13, column=0, columnspan=width // 6, sticky='W', pady=2)
            classical_work_combobox.grid(row=13, column=width // 6, columnspan=4, sticky='EW')
            classical_comment_label.grid(row=14, column=0, columnspan=width // 6, sticky='W', pady=2)
            classical_comment_combobox.grid(row=14, column=width // 6, columnspan=4, sticky='EW')
            classical_cut_label.grid(row=15, column=0, columnspan=width // 6, sticky='W', pady=2)
            classical_cut_entry.grid(row=15, column=width // 6, columnspan=4, sticky='EW')

    # event methods
    # track changes of comboboxes to update other comboboxes
    def url_combobox_write(*args):
        if url_combobox.get() in Globals.saved_urls:
            url = url_combobox.get()
            Globals.folder = Globals.saved_urls[url]['folder']
            output_folder_variable.set(
                'Folder: ' + (Globals.folder if Globals.folder else 'Default') + ' (click to open)')

            metadata_mode.set(Globals.saved_urls[url]['metadata_mode'])

    def combobox_write(*args):
        if metadata_mode.get() == 'vgm':
            artist: str = artist_combobox.get()
            album_combobox.set(artist if artist.endswith(' OST') else artist + ' OST')
        elif metadata_mode.get() == 'classical':
            # put the values from the comboboxes together to make the title
            artist: str = artist_combobox.get()
            type: str = classical_type_combobox.get()
            number: str = classical_number_combobox.get()
            key: str = classical_key_combobox.get()
            work: str = classical_work_combobox.get()
            comment: str = classical_comment_combobox.get()

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

            title_combobox.set("{0}{1}{2}{3}{4}".format(type,
                                                        ((' No. ' + number) if number else ''),
                                                        ((' in ' + real_key) if real_key else ''),
                                                        ((', ' + real_work) if real_work else ''),
                                                        (' (' + comment + ')' if comment else '')
                                                        ))

    # track change of window size
    def size_changed(event):
        try:
            error_text['height'] = (root.winfo_height() - download_frame.winfo_height() - metadata_frame.winfo_height()
                                    - 80) // 16
        except NameError:
            pass

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
    url_variable = StringVar()
    artist_variable = StringVar()
    artist_variable.set('Select the artist:')
    output_folder_variable = StringVar()
    output_folder_variable.set('Folder: Default (click to open)')
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

    classical_type_combobox_content = StringVar()
    classical_number_combobox_content = StringVar()
    classical_key_combobox_content = StringVar()
    classical_work_combobox_content = StringVar()
    classical_comment_combobox_content = StringVar()

    keep_artist_variable = StringVar()
    keep_artist_variable.set('0')

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

    # widgets
    # download widgets
    url_label = ttk.Label(download_frame, text='Input video/playlist URL, search query or saved URL name:')
    url_combobox = ttk.Combobox(download_frame, values=list(Globals.saved_urls.keys()), textvariable=url_variable)
    save_url_button = ttk.Button(download_frame, text='Save...', command=save_url)
    output_folder_label = ttk.Label(download_frame, textvariable=output_folder_variable)
    output_folder_button = ttk.Button(download_frame, text='Select output folder...', command=select_output_folder)
    download_button = ttk.Button(download_frame, text='Download', command=download)
    sync_ask_delete_checkbutton = ttk.Checkbutton(download_frame, text='Ask before deleting files',
                                                  variable=sync_ask_delete)
    progress_label = ttk.Label(download_frame, text='', textvariable=progress_text)
    download_progress = ttk.Progressbar(download_frame, orient=HORIZONTAL, mode='determinate', variable=progress_bar)
    video_label = ttk.Label(download_frame, text='', textvariable=video)

    # download widgets that get enabled/disabled
    download_widgets = [url_combobox, save_url_button, output_folder_button, download_button]

    # download mode dependent widgets
    download_mode_widgets = [sync_ask_delete_checkbutton]

    # metadata widgets
    select_metadata_label = ttk.Label(metadata_frame, text='', textvariable=select_metadata_variable, cursor='hand2')
    artist_label = ttk.Label(metadata_frame, textvariable=artist_variable)
    title_label = ttk.Label(metadata_frame, text='Select the title:')
    artist_combobox = ttk.Combobox(metadata_frame, textvariable=artist_combobox_content)
    swap_checkbutton = ttk.Checkbutton(metadata_frame, text='Swap title/artist', command=swap, variable=swap_variable)
    title_combobox = ttk.Combobox(metadata_frame)
    capitalize_artist_button = ttk.Button(metadata_frame, text='Normal capitalization', command=capitalize_artist,
                                          state='disabled')
    capitalize_title_button = ttk.Button(metadata_frame, text='Normal capitalization', command=capitalize_title,
                                         state='disabled')
    metadata_auto_button = ttk.Button(metadata_frame, text='Apply all metadata automatically',
                                      command=apply_metadata_auto, state='disabled')
    metadata_button = ttk.Button(metadata_frame, text='Apply metadata', command=apply_metadata_once, state='disabled')
    metadata_file_checkbutton = ttk.Checkbutton(metadata_frame, text='Apply metadata from metadata.json automatically',
                                                variable=metadata_file_variable, command=apply_metadata_file)

    # metadata widgets that get enabled/disabled
    metadata_widgets = [capitalize_artist_button, capitalize_title_button, metadata_auto_button, metadata_button]

    # metadata mode dependent widgets
    # vgm / album mode
    album_label = ttk.Label(metadata_frame, text='Select the album:')
    album_combobox = ttk.Combobox(metadata_frame)
    track_label = ttk.Label(metadata_frame, text='Select the track number:')
    track_combobox = ttk.Combobox(metadata_frame)
    keep_artist_checkbutton = ttk.Checkbutton(metadata_frame, text='Keep artist/album of previous video',
                                              variable=keep_artist_variable)
    # classical mode
    classical_type_label = ttk.Label(metadata_frame, text='Type:')
    classical_type_combobox = ttk.Combobox(metadata_frame, textvariable=classical_type_combobox_content)
    classical_number_label = ttk.Label(metadata_frame, text='Number:')
    classical_number_combobox = ttk.Combobox(metadata_frame, textvariable=classical_number_combobox_content)
    classical_key_label = ttk.Label(metadata_frame, text='Key:')
    classical_key_combobox = ttk.Combobox(metadata_frame, textvariable=classical_key_combobox_content)
    classical_work_label = ttk.Label(metadata_frame, text='Work:')
    classical_work_combobox = ttk.Combobox(metadata_frame, textvariable=classical_work_combobox_content)
    classical_comment_label = ttk.Label(metadata_frame, text='Comments:')
    classical_comment_combobox = ttk.Combobox(metadata_frame, textvariable=classical_comment_combobox_content)
    classical_cut_label = ttk.Label(metadata_frame, text='Cut:')
    classical_cut_entry = ttk.Entry(metadata_frame)

    metadata_mode_widgets = [album_label, album_combobox, track_label, track_combobox, keep_artist_checkbutton,
                             classical_type_label, classical_type_combobox, classical_number_label,
                             classical_number_combobox, classical_key_label, classical_key_combobox,
                             classical_work_label, classical_work_combobox, classical_comment_label,
                             classical_comment_combobox, classical_cut_label, classical_cut_entry]

    # error message widgets
    error_text = ScrolledText(error_frame, wrap=tkinter.WORD, height=10, state='disabled')

    # widget events
    url_variable.trace_add('write', url_combobox_write)
    output_folder_label.bind('<Button-1>', open_output_folder)
    select_metadata_label.bind('<Button-1>', open_url)
    artist_combobox_content.trace_add('write', combobox_write)
    classical_type_combobox_content.trace_add('write', combobox_write)
    classical_number_combobox_content.trace_add('write', combobox_write)
    classical_key_combobox_content.trace_add('write', combobox_write)
    classical_work_combobox_content.trace_add('write', combobox_write)
    classical_comment_combobox_content.trace_add('write', combobox_write)

    # grid (rows: 0-9 before mode dependent widgets, 10-19 mode dependent widgets, 20-29 after mode dependent widgets)
    width = 6  # number of columns

    download_frame.grid(row=0, column=0, sticky='NEW', padx=5, pady=5)
    url_label.grid(row=0, column=0, columnspan=width // 6, sticky='W')
    url_combobox.grid(row=0, column=width // 6, columnspan=4, sticky='EW')
    save_url_button.grid(row=0, column=width - width // 6, columnspan=width // 6, padx=(5, 0), sticky='W')
    output_folder_button.grid(row=1, column=0, pady=(5, 0), sticky='W')
    output_folder_label.grid(row=1, column=width // 6, columnspan=width - width // 6, sticky='W')
    download_button.grid(row=20, column=width // 6, pady=(5, 0), sticky='W')
    download_progress.grid(row=21, column=0, columnspan=width, sticky='EW')
    progress_label.grid(row=22, column=0, columnspan=width)
    video_label.grid(row=23, column=0, columnspan=width)

    metadata_frame.grid(row=1, column=0, sticky='NEW', padx=5, pady=5)
    select_metadata_label.grid(row=0, column=0, columnspan=width, sticky='W')
    artist_label.grid(row=1, column=0, columnspan=width // 6, sticky='W')
    artist_combobox.grid(row=1, column=width // 6, columnspan=4, sticky='EW')
    capitalize_artist_button.grid(row=1, column=5, padx=5, sticky='W')
    swap_checkbutton.grid(row=2, column=width // 6, columnspan=5, sticky='W')
    title_label.grid(row=3, column=0, columnspan=width // 6, sticky='W')
    title_combobox.grid(row=3, column=width // 6, columnspan=4, sticky='EW')
    capitalize_title_button.grid(row=3, column=5, padx=5, sticky='W')
    metadata_file_checkbutton.grid(row=20, column=0, pady=(5, 0), sticky='W')
    metadata_auto_button.grid(row=21, column=0, columnspan=1, pady=(5, 0), sticky='W')
    metadata_button.grid(row=21, column=width // 6, columnspan=4, pady=(5, 0), sticky='W')

    error_frame.grid(row=2, column=0, sticky='NEW', padx=5, pady=5)
    error_text.grid(row=0, column=0, columnspan=width, sticky='EW', pady=(5, 0))

    url_combobox.focus()

    root.columnconfigure(0, weight=1)

    for f in [download_frame, metadata_frame, error_frame]:
        for i in range(6):
            f.columnconfigure(i, weight=1)

    root.mainloop()


if __name__ == '__main__':
    main()
