# YouTube-Downloader
## Description
A GUI program that downloads YouTube videos and playlists, converts them to MP3 and lets you set metadata such as artist and title.

## Requirements
You need to have [ffmpeg](https://ffmpeg.org/download.html) for MP3 conversion to work.

## Download Modes
- Download: Input a video/playlist URL to download or a search query of which the first result will be downloaded. The resulting files will be converted to MP3 afterwards.
- Sync with folder: Specify an output folder where all downloaded files will be moved to after setting metadata. Videos which have already been downloaded and are in that folder will not be downloaded again. All files which are in the folder but not in the playlist will be deleted. You can enable asking before deleting a file.
- Calculate length of playlist: Input a playlist URL and the total playtime of the playlist will be calculated.
- Download metadata: Saves metadata such as title, uploader, tags or likes of a video or playlist to a `.json` file.
- Backup Playlist/Search for Changes: Saves ID, title, uploader and description of all videos in a playlist to a `.json` file. When that playlist has been saved before, the old and new playlist data are compared to determine which videos have been added to or deleted from that playlist. Those changes get saved to another `.json` file. This is useful if videos in a playlist have been deleted/made private by the uploader or because of a copyright claim, and you want to know the title.

## Metadata Modes
The program generates suggestions for the MP3 tags artist, title, album and track number based on the metadata of the video. You can also input your own data. These tags are saved to the MP3 file and can then be read by other programs such as MP3 players. There are different modes for setting metadata depending on the genre of music or type of playlist.

- Normal: Allows you to select artist and title. There is an option to swap the title and artist suggestions if the video shows them in different order. You can also apply metadata automatically, which will always save the first suggestion. All other modes extend the functions of this mode.
- Album: Should be used for playlists that contain a complete soundtrack or one album like on YouTube Music. You can select the album name and track number from suggestions or input your own. There is also an option to keep your previously set artist and album so that you don't have to change it for every video if you want the artist/album to be different from the suggestions.
- VGM: Should be used for downloading video game music. The same as Album mode, but words like "Music", "Soundtrack" or "Official" get filtered out. The album suggestion gets set to `artist name + OST`. For example: If the artist is "Super Mario Bros.", the album suggestion is set to "Super Mario Bros. OST".
- Classical: Should be used for downloading classical music as these videos tend to have inconsistent title formats. Important information about the piece is extracted from the title and put together in a consistent format. These are:
    - Type: e.g. Sonata, Piano Concerto, Symphony, String Quartet
    - Number: To specify which piece of the given type it is. Just the number has to be entered.
    - Key: The key of the piece. An uppercase letter means major, a lowercase letter means minor. A `b` or `s` added without a space denotes a flat or sharp key. Example: `cs` gets converted to "C Sharp Minor".
    - Work: The work number and movement information like number and tempo/name. It is the opus number (Op. # No. #) by default but some composers have different work formats, such as Mozart (K.) or Bach (BWV.), for which the title will be adjusted accordingly. Just the numbers have to be entered, separated by a space. Everything after the second space is interpreted as movement information. Example: The input `12 3 I. Prelude` gets converted to "Op. 12 No. 3: I. Prelude" if the composer has no special work format.
    - Comment: e.g. a nickname of the piece or instrumentation changes such as Piano/Orchestral/Instrumental arrangements
  
  All parameters except for the type are optional. The title is made from the parameters in the following way: `<type> No. <number> in <key>, <work> (<comment>)`

All metadata you choose gets saved to a `metadata.json` file and gets added to the suggestions if you download that video again. You can also select to automatically apply metadata that is already saved in `metadata.json`.

## External Modules Used
- [YouTube-DL](https://github.com/ytdl-org/youtube-dl) for downloading videos from YouTube
- [Mutagen](https://github.com/quodlibet/mutagen) for setting metadata in MP3 files
