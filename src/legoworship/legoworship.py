"""Main module."""

import csv
import os
import shutil
from pathlib import Path
from string import Template
from typing import ClassVar, Dict, List, Optional, Sequence, Type, TypeVar, Union

import attr
from loguru import logger
from pypinyin import lazy_pinyin

# The default pinyin order for "祢" is "mí" first and then "nǐ", which is not
# how we pronounce the character.
PINYIN_ADJUSTMENTS = {ord("祢"): "nǐ,mí"}


SONG_PAGE_TEMPLATE = Template(
    """---
layout: song
title: $title
permalink: /songbook/$title_url
---

#### 歌谱

{% include post-components/gallery.html
    columns = $data_columns
    full_width = true
    images = "$sheet_links,"
%}


"""
)

SONG_PAGE_BLANK_TEMPLATE = Template(
    """---
layout: song
title: $title
permalink: /songbook/$title_url
---

抱歉，暂时还未收录这首歌的谱子。

"""
)

T = TypeVar("T", bound="Song")


@attr.s(auto_attribs=True)
class Song:
    """A song."""

    title: str
    alternative_titles: Optional[List[str]] = None
    original_key: Optional[str] = None
    bpm: Optional[int] = None  # deprecate
    lyricist: Optional[str] = None
    composer: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    tempo: Optional[int] = None
    year: Optional[int] = None
    resources: Optional[List["SongResource"]] = None
    lyrics: Optional[str] = None

    @property
    def pinyin_title(self: T) -> List[str]:
        """Return the title in pinyin.

        Each letter is capitalized, to sort with English titles.

        Examples:
            >>> Song("歌曲").pinyin_title
            ['Ge', 'Qu']
            >>> Song("歌曲 a song").pinyin_title
            ['Ge', 'Qu', 'A', 'Song']

        Returns:
            A list of each character's pinyin
        """
        return [pinyin.title() for pinyin in lazy_pinyin(self.title.split(" "))]

    @property
    def title_url(self: T) -> str:
        """Replace spaces in the title with `+`."""
        return self.title.replace(" ", "+")

    @property
    def alternative_title_string(self: T) -> str:
        """Combine all alternative titles into one string."""
        return " / ".join(self.alternative_titles or [])

    @property
    def _data_columns(self: T) -> str:
        """Return the number of columns to be displayed in the song page."""
        if len(self.resources) <= 1:
            return "1"
        else:
            return "2"

    def match_file(self: T, filename: str, extensions: List[str]) -> bool:
        """Match if a filename contains the searched title or one of the extensions."""
        # to avoid files like 恩典之路（赞美之泉） matched by the song 赞美之泉.
        search_title = self.title.replace("祢", "你").replace("祂", "他")
        if search_title in filename and f"（{search_title}）" not in filename:
            for extension in extensions:
                if filename.endswith(extension):
                    return True
        return False

    def find_resources(
        self: T, resource_type: str, library: str, extension: Optional[str] = None
    ) -> bool:
        """Find and build song resources.

        Walk through each file in `library` and compare each song title with the filename,
        if there is a match, append it to a result list.

        Args:
            resource_type: "sheet" or "media".
            library: the path to search in.
            extension: match the extension if provided, otherwise a list of default
                extensions will be matched based on `resource_type`.

        Returns:
            True if resources are found, otherwise False

        Raises:
            ValueError: if `resource_type` does not match any of the default
                resource types.
        """
        if not extension and resource_type not in SongResource.EXTENSIONS:
            raise ValueError(f"Resource type of '{resource_type}' is not supported.")
        self.resources = [] if self.resources is None else self.resources
        search_extensions = [extension] if extension else SongResource.EXTENSIONS[resource_type]
        for root, _, files in os.walk(library):
            for file in files:
                if self.match_file(filename=file, extensions=search_extensions):
                    logger.debug(f"Found resource for {self.title}: {os.path.join(root, file)}.")
                    self.resources.append(
                        SongResource(
                            song=self,
                            type_=resource_type,
                            location=os.path.join(root, file),
                        )
                    )
        if not self.resources:
            logger.warning(f"Resource for {self.title} is not found.")
        return True if self.resources else False

    def move_resources(self: T, to: str, resource_type: str, subfolder: bool = True) -> bool:
        """Move all resources of a song to a desired directory."""
        if not self.resources:
            return False
        if subfolder:
            destination = os.path.join(to, self.title)
            try:
                os.mkdir(destination)
            except FileExistsError:
                logger.debug(f"Sheet folder for {self.title} already existed.")
        else:
            destination = to
        for resource in self.resources:
            if resource.type_ == resource_type:
                logger.debug(
                    f"Copying song {resource.song.title} from {resource.location} to {destination}."  # noqa: E501
                )
                shutil.copy2(src=resource.location, dst=destination)
        else:
            return True

    @property
    def _sheet_links(self: T) -> str:
        """Return a concatenated sheet link string."""
        sheet_locations = []
        if not self.resources:
            return ""
        for resource in self.resources:
            if resource.type_ == "sheet":
                sheet_location = resource.location.replace("docs/", "/")
                sheet_locations.append(sheet_location)
        return ",".join(sorted(sheet_locations))

    def check_page_exists(self: T, page_dir: str) -> bool:
        """Check if the song's page exists in `page_dir`."""
        # TODO: first should check if `page_dir` exists.
        if not os.path.isdir(page_dir):
            raise ValueError(f"{page_dir} is not a valid page directory.")
        return os.path.isfile(os.path.join(page_dir, self.title, ".md"))

    def create_page(self: T, page_dir: str, quiet: bool = False) -> bool:
        """Create a song's page if it does not exist."""
        # if self.check_page_exists(page_dir):
        #     error_message = f"Song page for {self.title} already exists."
        #     if quiet:
        #         logger.error(error_message)
        #         return False
        #     else:
        #         raise ValueError(error_message)
        song_page = os.path.join(page_dir, f"{self.title}.md")
        with open(song_page, "w") as f:
            f.write(
                SONG_PAGE_TEMPLATE.substitute(
                    title=self.title,
                    title_url=self.title_url,
                    sheet_links=self._sheet_links,
                    data_columns=self._data_columns,
                )
            )
        logger.debug(f"Successfully wrote song page {self.title}.")
        return True


S = TypeVar("S", bound="SongList")


@attr.s(auto_attribs=True)
class SongList:
    """A collection of `Song` instances.

    Args:
        name: the name of the song list, could be anything.
        songs: the list containing all songs.
    """

    _LEGACY_HEADER: ClassVar[List[str]] = ["name", "key", "hymn_ref", "sheet_type"]
    _HEADER: ClassVar[List[str]] = [
        "title",
        "original_key",
        "alternative_titles",
        "lyricist",
        "composer",
        "artist",
        "album",
        "tempo",
        "year",
    ]
    name: str
    songs: List[Song]

    @staticmethod
    def _sort_by_pinyin_title(song: Song) -> Sequence[Optional[str]]:
        """Sort function (by the pinyin title) used in self.sort()."""
        return song.pinyin_title

    @staticmethod
    def _sort_by_original_key(song: Song) -> Optional[str]:
        """Sort function (by the song's key) used in self.sort()."""
        return song.original_key

    def sort(self: S, by: str, desc: bool = False, legacy: bool = False) -> "SongList":
        """Order the list by any of the header item.

        Args:
            by: the sort key.
            desc: sort in descending order if True, else in ascending order.
            legacy: whether or not the format is legacy.

        Raises:
            NotImplementedError: if the sort key is a valid header but not yet implemented.
            ValueError: if the sort key is not a valid header item.

        Returns:
            A sorted `SongList` instance.
        """
        if (legacy and by in self._LEGACY_HEADER) or (not legacy and by in self._HEADER):
            if by == "title":
                sort_func = self._sort_by_pinyin_title
            elif by in ["key", "original_key"]:
                sort_func = self._sort_by_original_key
            else:
                raise NotImplementedError(f"Sorting by {by} is not supported.")
        else:
            raise ValueError(f"{by} is not a valid sort key.")

        sorted_songs = sorted(self.songs, key=sort_func, reverse=desc)
        return SongList(name=self.name, songs=sorted_songs)

    def export_csv(self: S, to: str, legacy: bool = False) -> bool:
        """Export the songlist to a csv file."""
        filenames = self._LEGACY_HEADER if legacy else self._HEADER
        with open(to, "w") as csv_file:
            csv_writer = csv.DictWriter(csv_file, fieldnames=filenames)
            csv_writer.writeheader()
            if legacy:
                for song in self.songs:
                    csv_writer.writerow(
                        {
                            "name": song.title,
                            "key": song.original_key,
                            "hymn_ref": None,
                            "sheet_type": None,
                        }
                    )
            else:
                for song in self.songs:
                    csv_writer.writerow(
                        {
                            "title": song.title,
                            "alternative_titles": song.alternative_title_string,
                            "original_key": song.original_key,
                            "lyricist": song.lyricist,
                            "composer": song.composer,
                            "artist": song.artist,
                            "album": song.album,
                            "tempo": song.tempo,
                            "year": song.year,
                        }
                    )
            return True

    def export_song_info(self: S, to: str) -> bool:
        """Export song resources and lyrics to docs/_data/song_info.yaml."""
        return True

    def _add_song(self: S, song: Song) -> bool:
        """Add a song to the list."""
        if isinstance(song, Song):
            self.songs.append(song)
            return True
        else:
            raise ValueError(f"Cannot add {song} ({type(song)}) to the song list.")

    def _add_song_list(self: S, songlist: "SongList") -> bool:
        """Add another song list to this song list."""
        if isinstance(songlist, SongList):
            self.songs = self.songs + songlist.songs
            return True
        else:
            raise ValueError(f"Cannot add {songlist} ({type(songlist)}) to the song list.")

    def add(self: S, songs: Union[Song, "SongList"]) -> bool:
        """Add another song or songlist to the song list."""
        if isinstance(songs, Song):
            self._add_song(songs)
            return True
        elif isinstance(songs, SongList):
            self._add_song_list(songs)
            return True
        else:
            raise ValueError(f"Cannot add {songs} ({type(songs)}) to the song list.")

    def find_resources(
        self: S, resource_type: str, library: str, extension: Optional[str] = None
    ) -> bool:
        """Find resources for every song in the list."""
        for song in self.songs:
            song.find_resources(resource_type, library, extension)
        return True

    def find_resources_in_subfolder(
        self: S, resource_type: str, library: str, extension: Optional[str] = None
    ) -> bool:
        """Find resources for every song in the list."""
        for song in self.songs:
            song.find_resources(resource_type, os.path.join(library, song.title), extension)
        return True

    def move_resources(self: S, to: str, resource_type: str, subfolder: bool = True) -> bool:
        """Move all resources."""
        if not self.songs:
            return False
        for song in self.songs:
            song.move_resources(to=to, resource_type=resource_type, subfolder=subfolder)
        else:
            return True

    def create_pages(self: S, page_dir: str, quiet: bool = False) -> bool:
        """Create a song page for all songs in the song list."""
        for song in self.songs:
            song.create_page(page_dir=page_dir, quiet=quiet)
        return True

    @classmethod
    def from_csv(cls: Type[S], csv_file_path: str, legacy: bool = False) -> S:
        """Generate a `SongList` instance from csv file.

        Args:
            csv_file_path: the file path stored songs data.
            legacy: whether or not the csv file to read is in legacy format.

        Returns:
            A `SongList` instance.

        Raises:
            ValueError: raise if the csv header is incorrect.

        # noqa: DAR101 cls
        """
        songs = []
        header = cls._LEGACY_HEADER if legacy else cls._HEADER
        with open(csv_file_path) as csv_file:
            csv_reader = csv.DictReader(csv_file)
            for line_count, row in enumerate(csv_reader):
                if line_count == 0:
                    if list(row.keys()) != header:
                        raise ValueError(f"Invalid csv header: {row.keys()}")
                    else:
                        logger.debug("The csv header is correctly read.")
                if legacy:
                    songs.append(Song(title=row["name"], original_key=row["key"]))
                else:
                    songs.append(
                        Song(
                            title=row["title"],
                            original_key=row["original_key"],
                            alternative_titles=row["alternative_titles"],
                            lyricist=row["lyricist"],
                            composer=row["composer"],
                            artist=row["artist"],
                            album=row["album"],
                            tempo=row["tempo"],
                            year=row["year"],
                        )
                    )
                    logger.debug(f"Added song {row['title']}")
        return cls(name=Path(csv_file_path).name, songs=songs)


@attr.s(auto_attribs=True)
class SongResource:
    """A music sheet or a media file for a song.

    Args:
        song: A `Song` instance linked to this resource.
        type_: either "sheet" or "media".
        location: the path pointing to the resource file.
        bpm: the beats per minutes (tempo) of the resource.
        key: the musical key of the resource.
        artist: the artist of the resource.
        album: the album of the resource.
    """

    EXTENSIONS: ClassVar[Dict[str, List[str]]] = {
        "sheet": [".png", ".pdf"],
        "media": [".mp3", ".m4a", ".wav"],
    }

    song: Song
    type_: str  # "sheet" or "media"
    location: str
    bpm: Optional[int] = None
    key: Optional[str] = None
    performer: Optional[str] = None
    album: Optional[str] = None


def find(title: str, what: str, path: str) -> Union[List[str], bool]:
    """Find a song in path."""
    if what not in ["sheet", "media"]:
        raise ValueError(f"Only `sheet` and `media` are supported, not {what}.")
    results = []
    for dirpath, _, files in os.walk(path):
        for filename in files:
            if what == "sheet":
                if title in filename and filename.endswith(".png") and "TINY" in dirpath:
                    found_path = os.path.join(dirpath, filename)
                    print(found_path)
                    results.append(found_path)
            elif what == "media":
                if title in filename and filename.endswith(".mp3"):
                    found_path = os.path.join(dirpath, filename)
                    print(found_path)
                    results.append(found_path)
            else:
                pass
    if not results:
        print(f"no results found for {title} in {path}")
        return False
    return results


def find_multiple(what: str, path: str, song_list: SongList) -> Union[List[str], bool]:
    """Find multiple _songs in a song list."""
    results = []
    for dirpath, _, files in os.walk(path):
        for filename in files:
            for song in song_list.songs:
                if song.title in filename and f"（{song.title}）" not in filename:
                    if (what == "sheet" and filename.endswith(".png") and "TINY" in dirpath) or (
                        what == "media" and filename.endswith(".mp3")
                    ):
                        found_path = os.path.join(dirpath, filename)
                        print(song.title)
                        print(found_path)
                        results.append(found_path)
    return results


if __name__ == "__main__":
    # import subprocess  # noqa
    # from pprint import pprint

    #
    SHEET_LIB = "/Users/kip/Mercury/3.Ecclasia/4. 灵栖清泉"
    MUSIC_LIB = "/Volumes/music"
    DOCS_SHEET_LIB = "docs/library/sheet"
    song_list = SongList.from_csv(csv_file_path="docs/_data/songs.csv", legacy=False)
    song_list.find_resources_in_subfolder("sheet", DOCS_SHEET_LIB, "png")
    # song_list.move_resources(to="docs/library/sheet", resource_type="sheet")
    # song = song_list.songs[-2]
    song_list.create_pages("docs/song/")
    # song.find_resources("sheet", library=SHEET_LIB, extension=".png")
    # song.move_resources(to="docs/library/sheet/", resource_type="sheet")
    # song_list = SongList.from_csv(csv_file_path="docs/_data/all_songs.csv", legacy=False)
    # song_list.sort(by="title").export_csv(to="docs/_data/songs.csv")
