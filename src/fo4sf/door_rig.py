"""Source-local door rig plan; source-derived output must remain local.

Preserves static ancestors and shape attachments so independently animated
nodes can become native rig bones without losing their parent transforms.
"""
import math
import struct
from . import nif, door_motion, door_clips


def quaternion_from_matrix(matrix):
    if len(matrix) != 9 or not all(math.isfinite(x) for x in matrix):
        raise nif.NifError('invalid door bind rotation matrix')
    for row in range(3):
        for other in range(3):
            dot = sum(matrix[3*row+k]*matrix[3*other+k] for k in range(3))
            if abs(dot - (1 if row == other else 0)) > 1e-4:
                raise nif.NifError('door bind rotation is not orthonormal')
    m = matrix
    determinant = m[0]*(m[4]*m[8]-m[5]*m[7])-m[1]*(m[3]*m[8]-m[5]*m[6])+m[2]*(m[3]*m[7]-m[4]*m[6])
    if abs(determinant-1)>1e-4:
        raise nif.NifError('door bind rotation is reflected')
    trace=m[0]+m[4]+m[8]
    if trace>0:
        s=math.sqrt(1+trace)*2
        result=[s/4,(m[7]-m[5])/s,(m[2]-m[6])/s,(m[3]-m[1])/s]
    else:
        i=max(range(3),key=lambda j:m[4*j]);j=(i+1)%3;k=(i+2)%3
        s=math.sqrt(1+m[4*i]-m[4*j]-m[4*k])*2
        result=[0]*4
        result[0]=(m[3*k+j]-m[3*j+k])/s
        result[i+1]=s/4
        result[j+1]=(m[3*j+i]+m[3*i+j])/s
        result[k+1]=(m[3*k+i]+m[3*i+k])/s
    length=math.hypot(*result)
    return [x/length for x in result]


def plan(source, samples_per_second=30, placed=False, aliases=None, allowed=None):
    """placed=True: the scene root's own stored transform counts as identity, as for a placed reference in game
    (nif.world_transforms(placed=True); docs/ai/research-log.md 2026-10-10). An animated scene root is then refused:
    its samples would carry the stored root transform the game leaves out.
    aliases: door_motion.inspect's {FO4 sequence: "Open" / "Close"}; an aliased object with an Open and no Close (the
    cog door's Stage2) closes by playing its Open backwards (door_clips.reversed_clip).
    allowed: door_motion.inspect's clip-slot names for an object that is no door (then no Close is made up)."""
    report=door_motion.inspect(source,aliases,allowed)
    if report['issues']:
        raise nif.NifError('door has absent or ambiguous animation bindings')
    roots=set(nif.footer_roots(source)) if placed else set()
    if roots & {t['node'] for sequence in report['sequences'] for t in sequence['targets']}:
        raise nif.NifError('placed door animates its scene root')
    nodes={i for i in range(len(source.blocks)) if source.type_of(i).endswith('Node')}
    parents={}
    for node in sorted(nodes):
        for child in nif.node_children(source,node):
            if child in parents and parents[child]!=node:
                raise nif.NifError('door node or shape has multiple parents')
            parents[child]=node
    shapes={s.block for s in nif.fo4_trishapes(source) if s.positions and s.triangles}
    required={t['node'] for sequence in report['sequences'] for t in sequence['targets']}
    required.update(parents[s] for s in shapes if s in parents)
    ordered=[];visited=set();active=set()
    def visit(node):
        if node in active:
            raise nif.NifError('cycle in door rig hierarchy')
        if node in visited:return
        active.add(node)
        if node in parents:visit(parents[node])
        active.remove(node);visited.add(node);ordered.append(node)
    for node in sorted(required):visit(node)
    indices={node:i for i,node in enumerate(ordered)}
    bones=[];binds={};names=set()
    for node in ordered:
        name_index,=struct.unpack_from('<i',source.blocks[node])
        name=source.strings[name_index].decode('latin-1') if 0<=name_index<len(source.strings) else ''
        if not name or name in names:
            raise nif.NifError('door rig bone name is empty or duplicate')
        names.add(name)
        translation,rotation,scale=nif._av_transform(source.blocks[node])
        if node in roots:
            translation,rotation,scale=(0.0,0.0,0.0),(1,0,0,0,1,0,0,0,1),1.0
        bind={'translation_source_units':list(translation),'quaternion_wxyz':quaternion_from_matrix(rotation),'scale':scale}
        # Validate unanimated bind channels too.
        bind=door_clips.sample_track(None,0,bind)
        binds[node]=bind
        bones.append({'node':node,'name':name,'parent':indices[parents[node]] if node in parents else -1,'bind':bind})
    attachments=[]
    for shape in sorted(shapes):
        if shape not in parents:
            raise nif.NifError('door shape lacks a rig attachment parent')
        t,r,s=nif._av_transform(source.blocks[shape])
        attachments.append({'shape':shape,'bone':indices[parents[shape]],
                            'local_transform':{'translation_source_units':list(t),'rotation_row_major':list(r),'scale':s}})
    clips=[door_clips.sample_sequence(sequence,binds,samples_per_second) for sequence in report['sequences']]
    if aliases and allowed is None and [c['name'] for c in clips]==['Open']:
        clips.append(door_clips.reversed_clip(clips[0]))
    # shader / visibility / particle tracks animate no node and stay out of the rig; listed so a manifest can say so
    return {'space':'source_local','bones':bones,'attachments':attachments,'clips':clips,
            'ignored_tracks':[dict(t) for t in report['ignored_targets']]}


def _qmul(a,b):
    aw,ax,ay,az=a;bw,bx,by,bz=b
    return [aw*bw-ax*bx-ay*by-az*bz,aw*bx+ax*bw+ay*bz-az*by,aw*by-ax*bz+ay*bw+az*bx,aw*bz+ax*by-ay*bx+az*bw]


def _qrotate(q,v):
    return _qmul(_qmul(q,[0,*v]),[q[0],-q[1],-q[2],-q[3]])[1:]


def is_identity_rotation(q,tolerance=1e-6):
    # w approaches +/-1 quadratically with angle; small authored rotations can
    # have an almost-identity w while their vector part is still significant.
    return abs(abs(q[0])-1)<=tolerance and math.hypot(*q[1:])<=tolerance


def animated_identity_binds(plan):
    """Copy of plan in which every animated bone has an identity bind rotation.

    Starfield door clips key each channel relative to the bone's bind (offline survey of 126 vanilla door rigs: all 391
    translation tracks of bones with a nonzero bind start at zero, all 83 rotation tracks of bones with a rotated bind
    start at identity; docs/ai/research-log.md 2026-10-12). Whether the engine applies a rotation offset before or after
    the bind is not known, so an animated FO4 node whose bind is rotated gets a static parent bone '<name>_Bind' holding
    that bind; the node itself gets an identity bind under it and its samples are re-expressed in the parent's space.
    Either composition order then reproduces FO4's pose. Shapes and child bones stay attached to the animated bone."""
    animated={t['node'] for clip in plan['clips'] for t in clip['tracks']}
    taken={b['name'].lower() for b in plan['bones']}
    bones=[];remap={};rebound={}
    for i,bone in enumerate(plan['bones']):
        parent=remap[bone['parent']] if bone['parent']!=-1 else -1
        bind=bone['bind']
        if bone['node'] in animated and not is_identity_rotation(bind['quaternion_wxyz']):
            if abs(bind['scale']-1)>1e-5:
                raise nif.NifError('animated door bone with a rotated, scaled bind is unsupported')
            name=bone['name']+'_Bind';k=2
            while name.lower() in taken:
                name=f"{bone['name']}_Bind{k}";k+=1
            taken.add(name.lower())
            bones.append({'node':None,'name':name,'parent':parent,'bind':dict(bind),'bind_for':bone['name']})
            parent=len(bones)-1
            rebound[bone['node']]=bind
            bind={'translation_source_units':[0.0,0.0,0.0],'quaternion_wxyz':[1.0,0.0,0.0,0.0],'scale':1.0}
        remap[i]=len(bones)
        bones.append({**bone,'parent':parent,'bind':bind})
    clips=[]
    for clip in plan['clips']:
        tracks=[]
        for track in clip['tracks']:
            bind=rebound.get(track['node'])
            if bind is not None:
                inverse=[bind['quaternion_wxyz'][0],*(-x for x in bind['quaternion_wxyz'][1:])]
                origin=bind['translation_source_units']
                track={**track,'samples':[{**s,'translation_source_units':_qrotate(inverse,[a-b for a,b in zip(
                    s['translation_source_units'],origin)]),'quaternion_wxyz':_qmul(inverse,s['quaternion_wxyz'])}
                    for s in track['samples']]}
            tracks.append(track)
        clips.append({**clip,'tracks':tracks})
    attachments=[{**a,'bone':remap[a['bone']]} for a in plan['attachments']]
    return {**plan,'bones':bones,'attachments':attachments,'clips':clips}


def rest_pose_issue(plan, units=0.5, degrees=2.0):
    """Why a door's clips do not rest at its bind pose, or None: the graph shows the bind pose while shut, so Open has to
    start there and Close end there. Of the 23 FO4 models the sliding / lifting route takes, 21 do (the ten audited ones
    exactly); BHMarketGateDoor01's bind is Open's end pose (170 degrees) and DExtMainGateDoor01's Close ends open (ArmTop
    43 degrees): review of PR #242."""
    binds={b['node']:b['bind'] for b in plan['bones'] if b.get('node') is not None}
    for clip in plan['clips']:
        if clip['name'] not in ('Open','Close'):continue
        for track in clip['tracks']:
            pose=track['samples'][0 if clip['name']=='Open' else -1];bind=binds[track['node']]
            q=bind['quaternion_wxyz'];turn=_qmul(pose['quaternion_wxyz'],[q[0],-q[1],-q[2],-q[3]])
            if (math.dist(pose['translation_source_units'],bind['translation_source_units'])>units
                    or math.degrees(2*math.acos(min(1.0,abs(turn[0]))))>degrees):
                return f"{clip['name']} of {track['name']} does not {'start' if clip['name']=='Open' else 'end'} at the bind pose"
    return None


def open_motion(plan, unit_scale, clip_name='Open'):
    """What each animated part does over a clip, for the manifest and offline checks: one row per track with its end
    offset in metres and its rotation in degrees (axis as a unit vector), both in model space (the bone's parent bind
    applied, scale included), from the first to the last sample. A vault door's upper panel reads travel_m [0, 0, 2.12]."""
    bones=plan['bones']
    world=[];world_scale=[]
    for bone in bones:
        q=bone['bind']['quaternion_wxyz'];s=bone['bind']['scale']
        world.append(list(q) if bone['parent']==-1 else _qmul(world[bone['parent']],q))
        world_scale.append(s if bone['parent']==-1 else world_scale[bone['parent']]*s)
    index={bone['node']:i for i,bone in enumerate(bones) if bone.get('node') is not None}
    rows=[]
    for clip in plan['clips']:
        if clip['name']!=clip_name:continue
        for track in clip['tracks']:
            i=index[track['node']];parent=bones[i]['parent']
            frame=world[parent] if parent!=-1 else [1.0,0.0,0.0,0.0]
            scale=world_scale[parent] if parent!=-1 else 1.0         # keys are in the parent's frame, its scale included
            first,last=track['samples'][0],track['samples'][-1]
            offset=[(b-a)*unit_scale*scale for a,b in zip(first['translation_source_units'],last['translation_source_units'])]
            q0=first['quaternion_wxyz'];q1=last['quaternion_wxyz']
            relative=_qmul(q1,[q0[0],-q0[1],-q0[2],-q0[3]])          # parent-space rotation taking the first pose to the last
            w=max(-1.0,min(1.0,abs(relative[0])));s=math.sqrt(max(0.0,1-w*w))
            axis=[x/s*(1 if relative[0]>=0 else -1) for x in relative[1:]] if s>1e-6 else None
            rows.append({'bone':bones[i]['name'],'travel_m':[round(x,4) for x in _qrotate(frame,offset)],
                         'rotation_deg':round(math.degrees(2*math.acos(w)),2),
                         'axis':[round(x,4) for x in _qrotate(frame,axis)] if axis else None})
    return rows


def slides(source, degrees=5.0, units=5.0):
    """True when an FO4 door's Open moves its parts without turning any of them (a sliding door whose name says nothing:
    Red Rocket's RedRPedDoor.nif, which the hinged template swung about the leaf's centre): every track turns less than
    degrees and one travels more than units (source units, 70 a metre). False when the motion cannot be read."""
    try:
        rows = open_motion(plan(source, placed=True), 1.0)
    except (nif.NifError, KeyError, ValueError, IndexError, struct.error):
        return False
    return bool(rows) and all(r['rotation_deg'] < degrees for r in rows) and \
        any(math.sqrt(sum(x * x for x in r['travel_m'])) > units for r in rows)


def flips(source, degrees=5.0, max_vertical=0.7):
    """True when an FO4 door's Open turns a part about a horizontal axis (a trapdoor or hatch leaf: the axis's z component
    is below max_vertical), which the vertical-hinge template cannot reproduce. False when the motion cannot be read."""
    try:
        rows = open_motion(plan(source, placed=True), 1.0)
    except (nif.NifError, KeyError, ValueError, IndexError, struct.error):
        return False
    return any(r['rotation_deg'] > degrees and r['axis'] and abs(r['axis'][2]) < max_vertical for r in rows)
