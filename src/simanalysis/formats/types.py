"""Verified Sims 4 DBPF resource type registry.

Primary source: S4TK @s4tk/models 0.6.14, MIT licensed.
Pinned source commit: 4345132fab79a92516095d22d9458b0db334dce5.
Source files:
- https://github.com/sims4toolkit/models/blob/4345132fab79a92516095d22d9458b0db334dce5/src/lib/enums/tuning-resources.ts
- https://github.com/sims4toolkit/models/blob/4345132fab79a92516095d22d9458b0db334dce5/src/lib/enums/binary-resources.ts
"""

from __future__ import annotations

import re
from enum import IntEnum


class TuningResourceType(IntEnum):
    """Resource types for XML tuning loaded by The Sims 4."""

    Achievement = 0x78559E9E
    AchievementCategory = 0x2451C101
    AchievementCollection = 0x04D2B465
    Action = 0x0C772E27
    Animation = 0xEE17C6AD
    Aspiration = 0x28B64675
    AspirationCategory = 0xE350DBD8
    AspirationTrack = 0xC020FCAD
    AwayAction = 0xAFADAC48
    Balloon = 0xEC6A8FC6
    Breed = 0x341D3F25
    Broadcaster = 0xDEBAFB73
    BucksPerk = 0xEC3DA10E
    Buff = 0x6017E896
    Business = 0x75D807F3
    BusinessRule = 0xB8E58C6C
    CallToAction = 0xF537B2E0
    Career = 0x73996BEB
    CareerEvent = 0x94420322
    CareerGig = 0xCCDB0EDD
    CareerLevel = 0x2C70ADF8
    CareerTrack = 0x48C75CE3
    CasMenu = 0x935A83C2
    CasMenuItem = 0x0CBA50F4
    CasPreferenceCategory = 0xCE04FC4B
    CasPreferenceItem = 0xEC68FD22
    CasStoriesAnswer = 0x80F12D17
    CasStoriesQuestion = 0x03246B9D
    CasStoriesTraitChooser = 0x8DAD1549
    Clan = 0xDEBEE6A5
    ClanValue = 0x998ED0AB
    ClubInteractionGroup = 0xFA0FFA34
    ClubSeed = 0x2F59B437
    ConditionalLayer = 0x9183DC91
    DetectiveClue = 0x537449F6
    DevelopmentalMilestone = 0xC5224F94
    DramaNode = 0x2553F435
    Ensemble = 0xB9881120
    GameRuleset = 0xE1477E18
    GuidanceTip = 0xD4A09ABD
    Headline = 0xF401205D
    HolidayDefinition = 0x0E316F6D
    HolidayTradition = 0x3FCD2486
    HouseholdMilestone = 0x3972E6F3
    Interaction = 0xE882D22F
    LotDecoration = 0xFE2DB1AB
    LotDecorationPreset = 0xDE1EF8FB
    LotTuning = 0xD8800D66
    LunarCycle = 0x55493B18
    Mood = 0xBA7B60B8
    Narrative = 0x3E753C39
    NotebookEntry = 0x9902FA76
    Object = 0xB61DE6B4
    ObjectPart = 0x7147A350
    ObjectState = 0x5B02819E
    Objective = 0x0069453E
    OpenStreetDirector = 0x4B6FDEC4
    PieMenuCategory = 0x03E9D964
    Posture = 0xAD6FDF1F
    RabbitHole = 0xB16AD2FA
    Recipe = 0xEB97F823
    Region = 0x51E7A18D
    RelationshipBit = 0x0904DF10
    RelationshipLock = 0xAE34E673
    Reward = 0x6FA49828
    RoleState = 0x0E4D15FB
    Royalty = 0x37EF2EE7
    Scommodity = 0x51077643
    Season = 0xC98DD45E
    ServiceNpc = 0x9CC21262
    Sickness = 0xC3FBD8DE
    SimFilter = 0x6E0DDA9F
    SimInfoFixup = 0xE2581892
    SimTemplate = 0x0CA4C78B
    Situation = 0xFBC3AEEB
    SituationGoal = 0x598F28E7
    SituationGoalSet = 0x9DF2F1F2
    SituationJob = 0x9C07855F
    SlotType = 0x69A5DAA4
    SlotTypeSet = 0x3F163505
    Snippet = 0x7DF2169C
    SocialGroup = 0x2E47A104
    Spell = 0x1F3413D9
    Statistic = 0x339BC5BD
    StoryArc = 0x602B1DAD
    StoryChapter = 0x4A864A3A
    Strategy = 0x6224C9D6
    Street = 0xF6E4CB00
    Subroot = 0xB7FF8F95
    TagSet = 0x49395302
    TemplateChooser = 0x48C2D5ED
    TestBasedScore = 0x4F739CEE
    Topic = 0x738E6C56
    Trait = 0xCB5FDDC7
    Tuning = 0x03B33DDF
    Tutorial = 0xE04A24A3
    TutorialTip = 0x8FB3E0B1
    University = 0xD958D5B1
    UniversityCourseData = 0x291CAFBE
    UniversityMajor = 0x2758B34B
    UserInterfaceInfo = 0xB8BF1A63
    Venue = 0xE6BBD7DE
    WalkBy = 0x3FD6243E
    WeatherEvent = 0x5806F5BA
    WeatherForecast = 0x497F3271
    Whim = 0x749A0636
    ZoneDirector = 0xF958A092
    ZoneModifier = 0x3C1D8799


class BinaryResourceType(IntEnum):
    """S4TK-supported binary resource types."""

    AnimationStateMachine = 0x02D5DF13
    CasPart = 0x034AEECB
    CasPartThumbnail = 0x3C1AF1F2
    CasPreset = 0xEAA32ADD
    CombinedTuning = 0x62E94D38
    DdsImage = 0xB6C8B6A0
    DstImage = 0x00B2D882
    Footprint = 0xD382BF57
    Light = 0x03B4C61D
    Model = 0x01661233
    ModelLod = 0x01D10F34
    NameMap = 0x0166038C
    ObjectCatalog = 0x319E4F1D
    ObjectCatalogSet = 0xFF56010C
    ObjectDefinition = 0xC0DB5AE7
    OpenTypeFont = 0x25796DCA
    PngImage = 0x2F7D0004
    RegionDescription = 0xD65DAFF9
    RegionMap = 0xAC16FBEC
    Rle2Image = 0x3453CF95
    RlesImage = 0xBA856C78
    Rig = 0x8EAF13DE
    SimData = 0x545AC67A
    SimInfo = 0x025ED6F4
    Slot = 0xD3044521
    StringTable = 0x220557DA
    TrayItem = 0x2A8A5E22
    TrueTypeFont = 0x276CA4B9


TUNING_TYPE_IDS = frozenset(int(item) for item in TuningResourceType)
BINARY_TYPE_IDS = frozenset(int(item) for item in BinaryResourceType)

TUNING_GENERIC = TuningResourceType.Tuning
SIMDATA = BinaryResourceType.SimData
STBL = BinaryResourceType.StringTable
CASP = BinaryResourceType.CasPart
OBJD = BinaryResourceType.ObjectDefinition
COBJ = BinaryResourceType.ObjectCatalog
COMBINED_TUNING = BinaryResourceType.CombinedTuning
DST_IMAGE = BinaryResourceType.DstImage
DDS_IMAGE = BinaryResourceType.DdsImage
RLE2_IMAGE = BinaryResourceType.Rle2Image
RLES_IMAGE = BinaryResourceType.RlesImage
PNG_IMAGE = BinaryResourceType.PngImage
MODL = BinaryResourceType.Model
MLOD = BinaryResourceType.ModelLod
GEOM = 0x015A1849

_DISPLAY_NAME_OVERRIDES = {
    int(BinaryResourceType.CasPart): "CAS Part",
    int(BinaryResourceType.CasPartThumbnail): "CAS Part Thumbnail",
    int(BinaryResourceType.CombinedTuning): "Combined Tuning",
    int(BinaryResourceType.DdsImage): "DDS Image",
    int(BinaryResourceType.DstImage): "DST Image",
    int(BinaryResourceType.ModelLod): "Model LOD",
    int(BinaryResourceType.ObjectCatalog): "Object Catalog",
    int(BinaryResourceType.ObjectCatalogSet): "Object Catalog Set",
    int(BinaryResourceType.ObjectDefinition): "Object Definition",
    int(BinaryResourceType.OpenTypeFont): "OpenType Font",
    int(BinaryResourceType.PngImage): "PNG Image",
    int(BinaryResourceType.Rle2Image): "RLE2 Image",
    int(BinaryResourceType.RlesImage): "RLES Image",
    int(BinaryResourceType.SimData): "SimData",
    int(BinaryResourceType.SimInfo): "Sim Info",
    int(BinaryResourceType.StringTable): "String Table",
    GEOM: "Geometry",
}
_BINARY_NAMES = {int(item): item.name for item in BinaryResourceType}
_TUNING_NAMES = {int(item): item.name for item in TuningResourceType}


def _split_camel(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", " ", name)


def is_tuning_type(resource_type: int | IntEnum) -> bool:
    """Return whether the resource type is one of the XML tuning classes."""
    return int(resource_type) in TUNING_TYPE_IDS


def type_name(resource_type: int | IntEnum) -> str:
    """Return a human-friendly resource type name, or ``Unknown``."""
    value = int(resource_type)
    if value in _DISPLAY_NAME_OVERRIDES:
        return _DISPLAY_NAME_OVERRIDES[value]
    if value in _BINARY_NAMES:
        return _split_camel(_BINARY_NAMES[value])
    if value in _TUNING_NAMES:
        tuning_name = _TUNING_NAMES[value]
        if tuning_name == "Tuning":
            return "Generic Tuning"
        return f"{_split_camel(tuning_name)} Tuning"
    return "Unknown"
