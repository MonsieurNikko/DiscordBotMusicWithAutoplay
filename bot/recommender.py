"""
Genre-Based Recommender with Weighted Random Selection
No database, all in-memory
"""
import re
import random
from collections import Counter
from dataclasses import dataclass


# Genre keyword mapping - keywords that indicate a genre
# Comprehensive list covering worldwide music genres
GENRE_KEYWORDS = {
    # ==================== ELECTRONIC / DANCE ====================
    "edm": [
        # Subgenres
        "edm", "electronic", "electro", "electronica", "dance music",
        "house", "deep house", "progressive house", "future house", "bass house", "tech house",
        "techno", "minimal techno", "detroit techno",
        "trance", "uplifting trance", "psytrance", "progressive trance", "vocal trance",
        "dubstep", "brostep", "riddim", "melodic dubstep",
        "drum and bass", "dnb", "liquid dnb", "neurofunk", "jungle",
        "hardstyle", "hardcore", "gabber", "happy hardcore",
        "future bass", "tropical house", "moombahton", "big room",
        "electro swing", "synthwave", "retrowave", "outrun",
        # Production terms
        "remix", "bootleg", "mashup", "drop", "bass drop", "bass boosted",
        "dj", "dj mix", "club mix", "festival", "rave",
        # Famous DJs/Producers
        "marshmello", "alan walker", "martin garrix", "avicii", "tiesto",
        "david guetta", "calvin harris", "deadmau5", "skrillex", "diplo",
        "zedd", "kygo", "illenium", "said the sky", "seven lions",
        "excision", "rezz", "virtual riot", "slander", "nghtmre",
        "armin van buuren", "above beyond", "gareth emery", "paul van dyk",
        "hardwell", "afrojack", "steve aoki", "dimitri vegas", "like mike",
        "porter robinson", "madeon", "flume", "odesza", "rufus du sol",
        "major lazer", "dj snake", "yellow claw", "r3hab", "don diablo",
    ],
    
    # ==================== BALLAD / SLOW ====================
    "ballad": [
        "ballad", "slow", "slow song", "power ballad",
        "acoustic", "unplugged", "live acoustic",
        "piano", "piano cover", "piano version",
        "emotional", "sad", "sad song", "heartbreak", "breakup",
        "love song", "romantic", "romance",
        # Vietnamese
        "nhạc buồn", "buồn", "tâm trạng", "nhạc tâm trạng",
        "ballad việt", "nhạc trữ tình", "trữ tình",
        "nhạc sến", "bolero",
        # Korean ballad
        "korean ballad", "kballad", "ost", "drama ost", "kdrama ost",
    ],
    
    # ==================== RAP / HIP-HOP ====================
    "rap": [
        # Main genres
        "rap", "hip hop", "hiphop", "hip-hop",
        "trap", "trap music", "drill", "uk drill", "ny drill",
        "underground", "underground rap",
        "boom bap", "old school hip hop", "new school",
        "mumble rap", "cloud rap", "emo rap", "rage",
        "gangsta rap", "g-funk", "west coast", "east coast",
        "southern hip hop", "dirty south", "crunk",
        # Terms
        "freestyle", "cypher", "bars", "flow", "beat", "producer",
        "diss track", "beef", "mixtape",
        # Vietnamese rappers
        "rap việt", "underground việt", "rapper việt",
        "đen vâu", "đen", "binz", "rhymastic", "karik", "suboi",
        "wowy", "gducky", "rpt mck", "rptonit", "obito", "low g",
        "dế choắt", "gonzo", "blacka", "lil wuyn", "andree",
        "seachains", "tage", "wxrdie", "hieuthuhai", "negav",
        "ban ca lang", "16 typh", "16typh", "sol7", "vsoul",
        # US/International rappers
        "eminem", "drake", "kendrick lamar", "j cole", "kanye west",
        "travis scott", "lil uzi vert", "playboi carti", "21 savage",
        "post malone", "juice wrld", "xxxtentacion", "lil peep",
        "migos", "future", "young thug", "gunna", "lil baby",
        "dababy", "roddy ricch", "pop smoke", "nba youngboy",
        "tyler the creator", "asap rocky", "denzel curry", "jid",
    ],
    
    # ==================== ROCK ====================
    "rock": [
        # Main genres
        "rock", "rock music", "rock and roll", "rock n roll",
        "hard rock", "classic rock", "soft rock",
        "alternative rock", "alt rock", "indie rock",
        "punk rock", "punk", "pop punk", "emo", "screamo",
        "metal", "heavy metal", "death metal", "black metal",
        "thrash metal", "nu metal", "metalcore", "deathcore",
        "progressive rock", "prog rock", "art rock",
        "grunge", "post grunge", "garage rock",
        "psychedelic rock", "stoner rock", "southern rock",
        # Terms
        "guitar solo", "guitar", "electric guitar", "riff",
        "live concert", "rock concert", "stadium rock",
        # Bands/Artists
        "the beatles", "led zeppelin", "pink floyd", "queen",
        "nirvana", "foo fighters", "red hot chili peppers", "rhcp",
        "linkin park", "green day", "blink 182", "my chemical romance",
        "paramore", "fall out boy", "panic at the disco",
        "metallica", "iron maiden", "black sabbath", "ac dc", "acdc",
        "guns n roses", "bon jovi", "aerosmith", "van halen",
        "arctic monkeys", "the strokes", "radiohead", "coldplay",
        "imagine dragons", "one republic", "onerepublic", "maroon 5",
        "twenty one pilots", "the 1975", "muse", "u2",
    ],
    
    # ==================== V-POP (Vietnamese Pop) ====================
    "vpop": [
        # General
        "vpop", "v-pop", "nhạc việt", "nhạc trẻ", "việt nam",
        "nhạc pop việt", "pop việt nam",
        # Male artists
        "sơn tùng", "sơn tùng mtp", "mtp", "sơn tùng m-tp",
        "jack", "j97", "jack 97",
        "erik", "đức phúc", "noo phước thịnh",
        "bùi anh tuấn", "khởi my", "kelvin khánh",
        "châu khải phong", "ưng hoàng phúc", "lam trường",
        "tuấn hưng", "đàm vĩnh hưng", "mr đàm",
        "quang lê", "đan trường", "phan mạnh quỳnh",
        "kay trần", "mono", "justatee", "binz",
        "soobin hoàng sơn", "hoàng dũng",
        "vũ", "vũ cát tường", "anh tú", "grey d", "greyd",
        # Female artists
        "mỹ tâm", "hồ ngọc hà", "thu minh",
        "đông nhi", "bích phương", "min", "amee",
        "hoàng thùy linh", "chi pu", "hương tràm",
        "văn mai hương", "thủy tiên", "phương ly",
        "thiều bảo trâm", "bảo anh", "hiền hồ",
        "tóc tiên", "hari won", "liz kim cương",
        "juky san", "orange", "lyly", "hòa minzy",
        "hương giang", "phương mỹ chi",
        # Groups
        "365", "365daband", "monstar", "uni5",
        # Gen Z artists
        "suni hạ linh", "rtee", "mr siro",
        "vicky nhung", "osad", "rpt orijinn",
    ],
    
    # ==================== K-POP ====================
    "kpop": [
        # General
        "kpop", "k-pop", "korean pop", "korean", "nhạc hàn",
        "kpop 2024", "kpop dance", "kpop cover",
        # Boy groups
        "bts", "bangtan", "방탄소년단",
        "exo", "nct", "nct 127", "nct dream", "wayv",
        "seventeen", "svt", "세븐틴",
        "stray kids", "skz", "straykids",
        "txt", "tomorrow x together",
        "enhypen", "ateez", "the boyz",
        "treasure", "monsta x", "got7", "2pm",
        "shinee", "super junior", "suju",
        "bigbang", "winner", "ikon", "zerobaseone",
        "riize", "boynextdoor",
        # Girl groups
        "blackpink", "블랙핑크", "twice", "트와이스",
        "red velvet", "레드벨벳", "aespa", "에스파",
        "itzy", "있지", "gidle", "g idle", "(g)i-dle",
        "ive", "아이브", "newjeans", "뉴진스",
        "le sserafim", "lesserafim", "nmixx",
        "mamamoo", "gfriend", "oh my girl",
        "2ne1", "girls generation", "snsd", "소녀시대",
        "everglow", "stayc", "fromis 9", "dreamcatcher",
        "loona", "이달의 소녀", "kep1er", "wjsn",
        "babymonster", "illit", "kiss of life",
        # Solo artists
        "iu", "아이유", "taeyeon", "sunmi", "chungha",
        "hwasa", "somi", "jennie", "rose", "rosé", "lisa",
        "jungkook", "jimin", "v", "suga", "rm", "jin",
        "baekhyun", "kai", "taemin", "key",
        "g dragon", "gd", "taeyang", "daesung",
        "zico", "dean", "crush", "jay park",
        # Labels
        "sm entertainment", "jyp", "yg", "hybe", "starship",
    ],
    
    # ==================== J-POP / J-ROCK ====================
    "jpop": [
        # General
        "jpop", "j-pop", "japanese", "nhạc nhật", "japan",
        "japanese pop", "japanese rock", "j-rock", "jrock",
        "anime", "anime opening", "anime ending", "anime op", "anime ed",
        "anisong", "vocaloid", "hatsune miku", "miku",
        "city pop", "japanese city pop",
        # Artists
        "yoasobi", "ado", "fujii kaze", "kenshi yonezu",
        "lisa", "aimer", "eve", "yorushika", "zutomayo",
        "radwimps", "one ok rock", "oor", "official hige dandism",
        "back number", "mrs green apple", "king gnu",
        "amazarashi", "uverworld", "asian kung fu generation",
        "bump of chicken", "spitz", "l'arc en ciel", "x japan",
        "babymetal", "band maid", "scandal",
        "utada hikaru", "ayumi hamasaki", "namie amuro",
        "arashi", "smap", "exile", "sandaime j soul brothers",
        "aimyon", "milet", "ikuta lilas", "imase", "tani yuuki",
        "higedan", "creepy nuts", "gesu no kiwami",
        # Idol groups
        "akb48", "nogizaka46", "keyakizaka46", "hinatazaka46",
        "morning musume", "perfume", "babymetal",
    ],
    
    # ==================== C-POP (Chinese Pop) ====================
    "cpop": [
        # General
        "cpop", "c-pop", "chinese", "mandopop", "cantopop",
        "nhạc trung", "nhạc hoa", "tiếng trung",
        "chinese pop", "taiwan pop", "hong kong pop",
        # Male artists
        "jay chou", "周杰倫", "eason chan", "陳奕迅",
        "wang leehom", "jj lin", "林俊傑",
        "eric chou", "周興哲", "jackson wang", "王嘉爾",
        "lu han", "lay zhang", "kris wu", "tao",
        "zhou shen", "周深", "hua chenyu", "華晨宇",
        "li ronghao", "张杰", "dimash",
        # Female artists
        "deng ziqi", "g.e.m.", "gem", "邓紫棋",
        "angela zhang", "張韶涵", "jolin tsai", "蔡依林",
        "hebe tien", "田馥甄", "alin", "a-lin",
        "taylor swift chinese", "bibi zhou", "周筆暢",
        # Groups
        "tfboys", "nine percent", "r1se",
        "snh48", "the9", "into1",
        # OST/Drama
        "chinese drama ost", "cdrama ost", "ancient drama",
    ],
    
    # ==================== LO-FI / CHILL ====================
    "lofi": [
        # Main genres
        "lofi", "lo-fi", "lo fi", "lofi hip hop",
        "chill", "chillhop", "chill hop", "jazz hop",
        "study music", "study beats", "focus music",
        "sleep music", "sleeping", "relax", "relaxing",
        "calm", "peaceful", "ambient", "atmospheric",
        "cafe music", "coffee shop", "work music",
        "meditation", "zen", "spa music",
        "rain sounds", "nature sounds", "asmr",
        # Channels/Artists
        "lofi girl", "chilledcow", "the jazz hop cafe",
        "college music", "homework radio",
        "nujabes", "j dilla", "tomppabeats", "jinsang",
        "idealism", "kupla", "bsd.u", "eevee",
    ],
    
    # ==================== POP (Western) ====================
    "pop": [
        # General
        "pop", "pop music", "pop song", "pop hit",
        "top 40", "top hits", "billboard", "chart",
        "mainstream", "radio hit", "trending", "viral",
        "tiktok", "tiktok song", "tiktok trend", "tiktok viral",
        # Subgenres
        "synth pop", "synthpop", "electropop", "dance pop",
        "indie pop", "chamber pop", "art pop", "baroque pop",
        "dream pop", "shoegaze", "noise pop",
        # Artists - Female
        "taylor swift", "ariana grande", "billie eilish",
        "dua lipa", "olivia rodrigo", "sabrina carpenter",
        "lady gaga", "beyonce", "rihanna", "katy perry",
        "selena gomez", "demi lovato", "miley cyrus",
        "adele", "sia", "lorde", "halsey", "charli xcx",
        "cardi b", "nicki minaj", "megan thee stallion",
        "doja cat", "sza", "tyla", "ice spice",
        "lana del rey", "marina", "grimes", "fka twigs",
        # Artists - Male
        "ed sheeran", "justin bieber", "shawn mendes",
        "harry styles", "zayn", "liam payne", "niall horan", "louis tomlinson",
        "bruno mars", "the weeknd", "charlie puth",
        "sam smith", "troye sivan", "hozier", "lewis capaldi",
        "john legend", "jason derulo", "chris brown",
        "bad bunny", "j balvin", "maluma", "daddy yankee",
        # Groups
        "one direction", "1d", "jonas brothers", "bts",
        "blackpink", "little mix", "fifth harmony",
    ],
    
    # ==================== R&B / SOUL ====================
    "rnb": [
        # Main genres
        "rnb", "r&b", "rhythm and blues", "soul", "neo soul",
        "contemporary r&b", "alternative r&b", "pnb",
        "funk", "disco", "motown",
        "new jack swing", "quiet storm",
        # Terms
        "smooth", "groove", "vibe", "vibes", "sensual",
        # Artists
        "the weeknd", "sza", "frank ocean", "daniel caesar",
        "h.e.r.", "summer walker", "jhene aiko", "kehlani",
        "bryson tiller", "6lack", "partynextdoor", "roy woods",
        "usher", "chris brown", "trey songz", "ne-yo",
        "alicia keys", "mary j blige", "brandy", "monica",
        "lauryn hill", "erykah badu", "jill scott", "maxwell",
        "d'angelo", "anderson paak", "silk sonic",
        "giveon", "lucky daye", "victoria monet", "chloe x halle",
        "brent faiyaz", "steve lacy", "omar apollo",
    ],
    
    # ==================== INDIE / ALTERNATIVE ====================
    "indie": [
        # Main genres
        "indie", "indie music", "independent", "alternative",
        "indie rock", "indie pop", "indie folk", "indie electronic",
        "bedroom pop", "hyperpop", "experimental", "avant garde",
        "post punk", "new wave", "gothic rock", "darkwave",
        "folk", "folk rock", "singer songwriter",
        "americana", "country folk", "bluegrass",
        # Artists
        "tame impala", "mac demarco", "rex orange county",
        "clairo", "beabadoobee", "phoebe bridgers", "boygenius",
        "wallows", "the neighbourhood", "role model",
        "steve lacy", "men i trust", "khruangbin",
        "vampire weekend", "mgmt", "foster the people",
        "glass animals", "alt-j", "two door cinema club",
        "bon iver", "sufjan stevens", "iron wine",
        "fleet foxes", "the lumineers", "of monsters and men",
        "hozier", "vance joy", "passenger", "james bay",
        "daughter", "london grammar", "florence machine",
    ],
    
    # ==================== JAZZ ====================
    "jazz": [
        "jazz", "jazz music", "smooth jazz", "acid jazz",
        "jazz fusion", "bebop", "swing", "big band",
        "free jazz", "modal jazz", "cool jazz", "hard bop",
        "jazz piano", "jazz guitar", "jazz saxophone",
        "miles davis", "john coltrane", "charlie parker",
        "louis armstrong", "duke ellington", "ella fitzgerald",
        "nina simone", "billie holiday", "sarah vaughan",
        "herbie hancock", "chick corea", "pat metheny",
        "kamasi washington", "robert glasper", "jacob collier",
    ],
    
    # ==================== CLASSICAL ====================
    "classical": [
        "classical", "classical music", "orchestra", "symphony",
        "piano classical", "violin", "cello", "orchestral",
        "opera", "baroque", "romantic era",
        "beethoven", "mozart", "bach", "chopin", "tchaikovsky",
        "vivaldi", "haydn", "brahms", "schubert", "liszt",
        "debussy", "ravel", "stravinsky", "shostakovich",
        "yo-yo ma", "lang lang", "yiruma", "ludovico einaudi",
        "hans zimmer", "john williams", "ennio morricone",
        "movie soundtrack", "film score", "cinematic",
    ],
    
    # ==================== COUNTRY ====================
    "country": [
        "country", "country music", "country song",
        "country rock", "country pop", "bro country",
        "outlaw country", "traditional country", "honky tonk",
        "bluegrass", "folk country", "americana",
        "nashville", "western", "cowboy",
        "luke combs", "morgan wallen", "zach bryan",
        "chris stapleton", "luke bryan", "jason aldean",
        "carrie underwood", "miranda lambert", "maren morris",
        "kacey musgraves", "taylor swift country",
        "johnny cash", "dolly parton", "willie nelson",
        "garth brooks", "george strait", "tim mcgraw",
    ],
    
    # ==================== LATIN ====================
    "latin": [
        "latin", "latino", "spanish", "español", "espanol",
        "reggaeton", "reggaetón", "perreo", "dembow",
        "latin trap", "trap latino",
        "salsa", "bachata", "merengue", "cumbia",
        "tango", "bossa nova", "samba",
        "flamenco", "spanish guitar",
        "bad bunny", "j balvin", "daddy yankee", "ozuna",
        "anuel aa", "rauw alejandro", "myke towers", "jhay cortez",
        "karol g", "becky g", "anitta", "rosalia", "rosalía",
        "shakira", "enrique iglesias", "ricky martin",
        "luis fonsi", "maluma", "nicky jam", "farruko",
        "sebastian yatra", "camilo", "raw alejandro",
    ],
    
    # ==================== REGGAE / DANCEHALL ====================
    "reggae": [
        "reggae", "reggae music", "roots reggae", "dub",
        "dancehall", "ragga", "ska", "rocksteady",
        "jamaica", "jamaican", "rasta", "rastafari",
        "bob marley", "peter tosh", "jimmy cliff",
        "damian marley", "stephen marley", "ziggy marley",
        "sean paul", "shaggy", "buju banton", "vybz kartel",
        "popcaan", "chronixx", "protoje", "koffee", "spice",
    ],
    
    # ==================== BOLERO / NHẠC VÀI====================
    "bolero": [
        "bolero", "nhạc vàng", "nhạc xưa", "nhạc trước 75",
        "nhạc sến", "tân nhạc", "quasi",
        "dương hồng loan", "lệ quyên", "đàm vĩnh hưng",
        "chế linh", "tuấn vũ", "như quỳnh",
        "phi nhung", "quang lê", "mạnh quỳnh",
        "thanh tuyền", "hương lan", "giao linh",
    ],
    
    # ==================== NHẠC TRỮ TÌNH / QUẾHƯƠNG ====================
    "truitinh": [
        "trữ tình", "nhạc trữ tình", "quê hương",
        "dân ca", "nhạc dân ca", "ca trù", "quan họ",
        "nhạc cách mạng", "nhạc đỏ",
        "ru con", "lullaby", "nhạc thiếu nhi",
        "tân cổ giao duyên", "cải lương", "vọng cổ",
        "hát văn", "hát xẩm", "hát chèo",
    ],
    
    # ==================== NHẠC PHIM / OST ====================
    "ost": [
        "ost", "soundtrack", "original soundtrack",
        "movie soundtrack", "film soundtrack",
        "nhạc phim", "nhạc phim việt", "nhạc phim hàn",
        "drama ost", "kdrama ost", "cdrama ost",
        "game soundtrack", "game ost", "video game music",
        "anime ost", "anime soundtrack",
        "musical", "broadway", "disney",
    ],
    
    # ==================== WORSHIP / GOSPEL ====================
    "worship": [
        "worship", "praise", "gospel", "christian",
        "hillsong", "bethel", "elevation worship",
        "maverick city", "chris tomlin", "lauren daigle",
        "nhạc thánh", "thánh ca", "nhạc đạo",
    ],
    
    # ==================== PHONK / DRIFT ====================
    "phonk": [
        "phonk", "drift phonk", "brazilian phonk",
        "memphis rap", "cowbell", "aggressive phonk",
        "gym phonk", "workout phonk", "dark phonk",
        "ghostemane", "kordhell", "dvrst", "playaphonk",
    ],
}

# Search queries for each genre (used to find similar songs)
GENRE_SEARCH_QUERIES = {
    "edm": ["edm remix 2024", "best edm drops", "festival music", "electronic dance"],
    "ballad": ["ballad hay nhất 2024", "sad songs playlist", "nhạc buồn hay", "acoustic covers"],
    "rap": ["rap việt hay 2024", "hip hop 2024", "underground rap hot", "trap music"],
    "rock": ["rock songs 2024", "best rock music", "rock playlist", "alternative rock"],
    "vpop": ["vpop hay nhất 2024", "nhạc trẻ mới nhất", "nhạc việt hot", "vpop trending"],
    "kpop": ["kpop 2024", "best kpop songs", "kpop playlist", "kpop dance"],
    "jpop": ["jpop 2024", "japanese music", "anime songs", "jpop playlist"],
    "cpop": ["cpop 2024", "chinese pop songs", "mandopop playlist", "nhạc hoa hay"],
    "lofi": ["lofi hip hop", "lofi chill beats", "study music playlist", "relaxing music"],
    "pop": ["pop songs 2024", "top hits 2024", "viral songs", "trending music"],
    "rnb": ["rnb 2024", "r&b songs", "neo soul playlist", "smooth rnb"],
    "indie": ["indie music 2024", "indie playlist", "alternative songs", "bedroom pop"],
    "jazz": ["jazz music", "smooth jazz", "jazz playlist", "jazz café"],
    "classical": ["classical music", "piano classical", "orchestra music", "relaxing classical"],
    "country": ["country songs 2024", "country music playlist", "new country"],
    "latin": ["latin music 2024", "reggaeton playlist", "latin hits", "bachata"],
    "reggae": ["reggae music", "reggae playlist", "dancehall 2024", "roots reggae"],
    "bolero": ["bolero hay nhất", "nhạc vàng hay", "nhạc sến hay nhất"],
    "truitinh": ["nhạc trữ tình hay", "nhạc quê hương", "dân ca việt nam"],
    "ost": ["nhạc phim hay", "drama ost", "movie soundtrack", "anime ost"],
    "worship": ["worship songs 2024", "praise music", "gospel playlist"],
    "phonk": ["phonk music 2024", "drift phonk playlist", "aggressive phonk"],
}



@dataclass
class TrackInfo:
    """Minimal track info for history"""
    video_id: str
    title: str
    channel: str
    duration_ms: int


class GenreRecommender:
    """
    Genre-based recommender with weighted random selection.
    Learns genres from last N songs, recommends similar genre with variety.
    """
    
    def __init__(self, history_limit: int = 10, anti_repeat_limit: int = 20):
        self.history_limit = history_limit
        self.anti_repeat_limit = anti_repeat_limit
        
        # Per-guild state
        self._guild_history: dict[int, list[TrackInfo]] = {}
        self._guild_recent_ids: dict[int, list[str]] = {}
        self._guild_genre_counts: dict[int, Counter] = {}
    
    def learn(self, guild_id: int, track: TrackInfo) -> None:
        """Record a played track for learning."""
        # Initialize if needed
        if guild_id not in self._guild_history:
            self._guild_history[guild_id] = []
            self._guild_recent_ids[guild_id] = []
            self._guild_genre_counts[guild_id] = Counter()
        
        # Add to history
        self._guild_history[guild_id].append(track)
        if len(self._guild_history[guild_id]) > self.history_limit:
            old_track = self._guild_history[guild_id].pop(0)
            # Decrease genre count for removed track
            old_genre = self._detect_genre(old_track.title)
            if old_genre and self._guild_genre_counts[guild_id][old_genre] > 0:
                self._guild_genre_counts[guild_id][old_genre] -= 1
        
        # Add to recent IDs (for anti-repeat)
        self._guild_recent_ids[guild_id].append(track.video_id)
        if len(self._guild_recent_ids[guild_id]) > self.anti_repeat_limit:
            self._guild_recent_ids[guild_id].pop(0)
        
        # Learn genre
        genre = self._detect_genre(track.title)
        if genre:
            self._guild_genre_counts[guild_id][genre] += 1
    
    def get_recent_ids(self, guild_id: int) -> set[str]:
        """Get video IDs to avoid repeating."""
        return set(self._guild_recent_ids.get(guild_id, []))
    
    def _detect_genre(self, title: str) -> str:
        """Detect genre from title using keyword mapping."""
        title_lower = title.lower()
        
        genre_scores = {}
        for genre, keywords in GENRE_KEYWORDS.items():
            score = 0
            for keyword in keywords:
                if keyword in title_lower:
                    # Longer keywords get higher weight
                    score += len(keyword.split())
            if score > 0:
                genre_scores[genre] = score
        
        if genre_scores:
            # Return genre with highest score
            return max(genre_scores, key=genre_scores.get)
        
        return "pop"  # Default genre
    
    def build_queries(self, guild_id: int, current_title: str) -> list[str]:
        """
        Build search queries based on detected genre.
        Returns multiple queries for diversity.
        """
        queries = []
        
        # Detect genre of current song
        current_genre = self._detect_genre(current_title)
        
        # Get most listened genres for this guild
        genre_counts = self._guild_genre_counts.get(guild_id, Counter())
        top_genres = [g for g, _ in genre_counts.most_common(3)]
        
        # Add current genre if not in top
        if current_genre and current_genre not in top_genres:
            top_genres.insert(0, current_genre)
        
        # Build queries from genres
        for genre in top_genres[:3]:
            if genre in GENRE_SEARCH_QUERIES:
                # Pick a random query for this genre
                query = random.choice(GENRE_SEARCH_QUERIES[genre])
                queries.append(query)
        
        # Fallback: cleaned current title
        if not queries:
            cleaned = self._clean_title(current_title)
            if cleaned:
                queries.append(cleaned)
        
        return queries[:3]  # Max 3 queries
    
    def score_candidate(self, guild_id: int, title: str, channel: str) -> float:
        """
        Score a candidate track based on genre matching.
        Higher = better match.
        """
        candidate_genre = self._detect_genre(title)
        genre_counts = self._guild_genre_counts.get(guild_id, Counter())
        
        # Base score from genre popularity in history
        score = genre_counts.get(candidate_genre, 0) * 15
        
        # Bonus for matching current trend
        if genre_counts:
            top_genre = genre_counts.most_common(1)[0][0]
            if candidate_genre == top_genre:
                score += 20
        
        # Slight diversity bonus for less common genres
        total_plays = sum(genre_counts.values())
        if total_plays > 0:
            genre_ratio = genre_counts.get(candidate_genre, 0) / total_plays
            if genre_ratio < 0.3:  # Minority genre
                score += 10  # Diversity bonus
        
        return max(score, 5)  # Minimum score of 5
    
    def select_with_randomness(self, candidates: list[tuple], randomness: float = 0.3) -> tuple:
        """
        Select a candidate using weighted random selection.
        
        Args:
            candidates: List of (score, track_data) tuples
            randomness: 0.0 = always pick best, 1.0 = fully random
        
        Returns:
            Selected (score, track_data) tuple
        """
        if not candidates:
            return None
        
        if len(candidates) == 1:
            return candidates[0]
        
        # Sort by score descending
        sorted_candidates = sorted(candidates, key=lambda x: x[0], reverse=True)
        
        # Calculate weighted probabilities
        scores = [c[0] for c in sorted_candidates]
        min_score = min(scores)
        max_score = max(scores)
        
        if max_score == min_score:
            # All same score, random pick
            return random.choice(sorted_candidates)
        
        # Normalize scores to weights
        weights = []
        for score in scores:
            # Higher score = higher weight, but add randomness factor
            normalized = (score - min_score) / (max_score - min_score)
            # Blend between score-based and uniform distribution
            weight = (1 - randomness) * normalized + randomness * (1 / len(candidates))
            weights.append(max(weight, 0.01))  # Minimum weight
        
        # Weighted random selection
        selected = random.choices(sorted_candidates, weights=weights, k=1)[0]
        return selected
    
    def _clean_title(self, title: str) -> str:
        """Remove noise from title for better search queries."""
        cleaned = title
        
        # Remove common noise patterns
        patterns = [
            r'\[.*?\]',           # [Official MV], [Lyrics]
            r'\(.*?\)',           # (Official Audio)
            r'Official\s*(MV|Video|Audio|Lyric|Music\s*Video)',
            r'MV|M/V|Lyrics?|Lyric\s*Video',
            r'HD|4K|8D|Audio',
            r'ft\.?|feat\.?',
            r'\|.*$',             # Everything after |
            r'#\w+',              # Hashtags
        ]
        
        for pattern in patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        # Normalize whitespace
        cleaned = ' '.join(cleaned.split())
        
        # Keep max 6 tokens
        tokens = cleaned.split()[:6]
        return ' '.join(tokens)
    
    def get_genre_stats(self, guild_id: int) -> dict:
        """Get genre listening stats for a guild."""
        return dict(self._guild_genre_counts.get(guild_id, {}))
    
    def clear_guild(self, guild_id: int) -> None:
        """Clear history for a guild (e.g., when bot leaves)."""
        self._guild_history.pop(guild_id, None)
        self._guild_recent_ids.pop(guild_id, None)
        self._guild_genre_counts.pop(guild_id, None)


# Global instance - backward compatible name
recommender = GenreRecommender()
