"""External CALUMI native door writer: a door's own rig and Open/Close clips.

Explicit scale factor and source-local basis required. Outputs are source-derived
assets and must remain outside the repository. Event data is retained in a
sidecar for future graph integration, not encoded as working runtime events.

Clip layout follows vanilla Starfield door clips (offline survey of 126 vanilla
door rigs + open clips read back with CALUMI; docs/ai/research-log.md 2026-10-12):
only animated bones carry a track, and keys are offsets from the bone's bind
(translation starts at zero, rotation at identity). Animated bones must have an
identity bind rotation (door_rig.animated_identity_binds), so the unknown order
in which the engine composes a rotation offset with the bind cannot matter.
"""
import ctypes as c
import math
import pathlib
import json
import tempfile
import xml.etree.ElementTree as ET
from .nif import NifError
from . import door_rig

MOVE_EPSILON = 1e-6     # metres: a translation offset below this is "no translation channel"


# frames off the 30 fps grid still accepted: FO4 stores clip times as float32, so the cog door's 43 1/3 s Stage2 reads
# 43.333343505859375 s = 1300.0003 frames (PC build 01ee50e); a thousandth of a frame is far above that rounding and far
# below a real off-grid key
GRID_TOLERANCE = 1e-3


def prepare(plan, unit_scale, fps=30):
    if not math.isfinite(unit_scale) or unit_scale <= 0 or fps != 30:
        raise NifError('native prototype requires positive unit scale and 30 fps')
    bones=plan['bones']
    if not bones or plan['space']!='source_local':raise NifError('native writer requires a source-local rig')
    for i,bone in enumerate(bones):
        if bone['parent'] < -1 or bone['parent'] >= i or abs(bone['bind']['scale']-1)>1e-5:
            raise NifError('native prototype requires ordered bones with unit bind scale')
    index={door_rig.bone_key(bone):i for i,bone in enumerate(bones)}
    clips=[]
    for clip in plan['clips']:
        last=round(clip['duration']*fps)
        if not 0<=last<=65535 or abs(last-clip['duration']*fps)>GRID_TOLERANCE:
            raise NifError('native door duration is not on the 30 fps grid')
        tracks=[]
        for source in clip['tracks']:
            if source['node'] not in index:
                raise NifError('door clip track has no rig bone')
            bone_index=index[source['node']];bone=bones[bone_index];bind=bone['bind']
            static=bool(source.get('static'))        # anim_object.fill_static_tracks: a bone that stays at its bind pose, still given its block
            if not static and not door_rig.is_identity_rotation(bind['quaternion_wxyz']):
                raise NifError('animated door bone needs an identity bind rotation (door_rig.animated_identity_binds)')
            frames={};previous=None
            for sample in source['samples']:
                frame=round(sample['elapsed']*fps)
                if not 0<=frame<=last or abs(frame-sample['elapsed']*fps)>GRID_TOLERANCE:
                    raise NifError('native door sample is not on the 30 fps grid')
                if abs(sample['scale']-1)>1e-5:
                    raise NifError('animated door scale is not supported')
                q=[1.0,0.0,0.0,0.0] if static else list(sample['quaternion_wxyz']);length=math.sqrt(sum(x*x for x in q))
                q=[x/length for x in q]
                if previous is not None and sum(a*b for a,b in zip(q,previous))<0:
                    q=[-x for x in q]                    # keep one hemisphere: no spurious 360 degree spin
                previous=q
                frames[frame]={'frame':frame,'quaternion_wxyz':q,
                               'translation':[(a-b)*unit_scale for a,b in zip(sample['translation_source_units'],
                                                                             bind['translation_source_units'])] if not static else [0.0,0.0,0.0]}
            keys=[frames[f] for f in sorted(frames)]
            moves=any(abs(x)>MOVE_EPSILON for k in keys for x in k['translation'])
            tracks.append({'name':bone['name'],'bone':bone_index,'keys':keys,
                           'channels':['rotation','translation'] if moves else ['rotation']})
        tracks.sort(key=lambda t:t['bone'])
        clips.append({'name':clip['name'],'tracks':tracks,'events':clip['events'],'duration':clip['duration']})
    return {'bones':bones,'clips':clips,'unit_scale':unit_scale,'fps':fps}


def clip_descriptor(name):
    """New .afx discovery descriptor matching native Open/Close tag metadata.

    No game graph is copied or altered. Relative filename resolves beside .afx.
    This does not provide source sound/quest events or graph activation itself.
    """
    if name not in ('Open', 'Close'):
        raise ValueError('unsupported door clip name')
    root = ET.Element('root')
    ET.SubElement(root, 'is_state').text = '0'
    ET.SubElement(root, 'tag').text = name
    ET.SubElement(root, 'filename').text = name + '.af'
    return ET.tostring(root, encoding='utf-8')


def export(plan, dll, output, unit_scale, descriptors=None):
    """descriptors: {clip name: .afx bytes} for an object that is no door (anim_object); the clip names are then exactly its keys.
    None: the door's Open / Close and their descriptors."""
    prepared=prepare(plan,unit_scale)
    allowed=set(descriptors) if descriptors is not None else {'Open','Close'}
    output=pathlib.Path(output).resolve()
    repo=pathlib.Path(__file__).resolve().parents[2]
    if output==repo or repo in output.parents:raise ValueError('native assets must stay outside repository')
    output.mkdir(parents=True,exist_ok=True)
    lib=c.CDLL(str(pathlib.Path(dll).resolve()))
    p=c.c_void_p;b=c.c_bool
    def bind(name,args,result):
        fn=getattr(lib,name);fn.argtypes=args;fn.restype=result;return fn
    error=bind('CreateStringContainerC',[],p)()
    message=bind('GetStringFromContainerC',[p],c.c_char_p)
    def require(result):
        if not result:raise RuntimeError((message(error) or b'CALUMI operation failed').decode(errors='replace'))
        return result
    rig=bind('CreateSkeletonRigC',[c.c_char_p],p)(b'FO4Port_DoorPrototype')
    try:
        require(rig)
        require(bind('SFBGSRigPackage_AddPackageToSkeletonRigC',[p,p,b],b)(rig,error,True))
        add=bind('AddBoneToSkeletonRigC',[p]+[c.c_float]*7+[c.c_char_p,c.c_int,b,p],b)
        for bone in prepared['bones']:
            pose=bone['bind'];w,x,y,z=pose['quaternion_wxyz'];t=[v*unit_scale for v in pose['translation_source_units']]
            require(add(rig,x,y,z,w,*t,bone['name'].encode('utf-8'),bone['parent'],True,error))
        rigpath=output/'door.rig'
        require(bind('SaveSkeletonRigToSFBGSFormatDirectC',[p,c.c_wchar_p,p],b)(rig,str(rigpath),error))
        for clip in prepared['clips']:
            if clip['name'] not in allowed:raise ValueError('unsupported door clip name')
            anim=bind('CreateAnimationC',[c.c_char_p,c.c_uint],p)(clip['name'].encode(),len(prepared['bones']))
            try:
                require(anim)
                for track in clip['tracks']:
                    # the block index is the RIG bone index (CALUMI files the block under it and checks the name)
                    block=bind('CreateAnimBlockC',[c.c_char_p,c.c_int,p],p)(track['name'].encode('utf-8'),track['bone'],error)
                    require(block)
                    try:
                        for key in track['keys']:
                            w,x,y,z=key['quaternion_wxyz']
                            channels=[('Rotation',[c.c_uint16]+[c.c_float]*4,[key['frame'],x,y,z,w])]
                            if 'translation' in track['channels']:
                                channels.append(('Translation',[c.c_uint16]+[c.c_double]*3,[key['frame'],*key['translation']]))
                            for kind,args,values in channels:
                                entry=bind('Create'+kind+'EntryC',args,p)(*values)
                                require(entry)
                                try:require(bind('Add'+kind+'SqToAnimBlockC',[p,p,c.c_uint,b],b)(block,entry,1,True))
                                finally:bind('Delete'+kind+'EntryC',[p],b)(entry)
                        require(bind('AddAnimBlockToAnimationC',[p,p,b,p],b)(anim,block,True,error))
                        block=None # ownership transferred/deleted by successful native call
                    finally:
                        if block:bind('DeleteAnimationBlockC',[p],b)(block)
                require(bind('SaveAnimationToSFBGSFormatDirectC',[p,c.c_wchar_p,p,p],b)(anim,str(output/(clip['name']+'.af')),rig,error))
                (output/(clip['name']+'.afx')).write_bytes(descriptors[clip['name']] if descriptors is not None else clip_descriptor(clip['name']))
            finally:
                if anim:bind('DeleteAnimationC',[p],b)(anim)
        (output/'events.json').write_text(json.dumps({'runtime_events_encoded':False,'clips':[
            {'name':clip['name'],'duration':clip['duration'],'events':clip['events']} for clip in prepared['clips']]},indent=2))
        return prepared
    finally:
        if rig:bind('DeleteSkeletonRigC',[p],b)(rig)
        bind('DeleteStringContainerC',[p],None)(error)


# where a door's own rig and clips sit next to its NIF, as in vanilla (<door folder>/characterassets/skeleton.rig,
# <door folder>/animations/<clip>.af + .afx); the DOOR record's BNAM / CNAM name these paths below Meshes\
RIG_FILE = 'characterassets/skeleton.rig'
CLIP_DIR = 'animations'


def export_files(plan, dll, unit_scale, exporter=None, descriptors=None):
    """Rig + Open/Close clips + .afx descriptors as {relative path: bytes} (RIG_FILE, CLIP_DIR/<name>.af/.afx).
    Written through a temporary folder outside the repository; the events sidecar is not part of the result."""
    exporter=exporter or export
    with tempfile.TemporaryDirectory(prefix='fo4port-door-') as tmp:
        prepared=exporter(plan,dll,tmp,unit_scale) if descriptors is None else exporter(plan,dll,tmp,unit_scale,descriptors=descriptors)
        out={RIG_FILE:(pathlib.Path(tmp)/'door.rig').read_bytes()}
        for clip in prepared['clips']:
            for suffix in ('.af','.afx'):
                out[f"{CLIP_DIR}/{clip['name']}{suffix}"]=(pathlib.Path(tmp)/(clip['name']+suffix)).read_bytes()
    return out
