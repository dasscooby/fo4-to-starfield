import struct
import unittest
from unittest.mock import patch
from test_door_motion import fixture
from fo4sf import door_collision,door_rig,fo4collision as fc,nif

class SharedSystem:
    def objects(self):return [(0,'hknpPhysicsSystemData'),(1000,'hknpDynamicCompoundShape'),(2000,'hknpDynamicCompoundShape')]
    def array(self,off):return 100,2
    def pointer(self,off):return 1000 if off==100 else 2000
    def unpack(self,fmt,off):return (0,0,0,1) if fmt=='<4f' else (-1 if off<196 else 1,0,0)

class DoorCollisionOwnershipTests(unittest.TestCase):
    def source(self):
        source=fixture();data=source.add_block('bhkPhysicsSystem',struct.pack('<I',4)+b'test')
        source.add_block('bhkNPCollisionObject',struct.pack('<iHiI',1,128,data,0))
        source.add_block('bhkNPCollisionObject',struct.pack('<iHiI',2,128,data,1))
        return source
    def test_shared_system_distinct_body_ids_and_bones(self):
        source=self.source();rig=door_rig.plan(source)
        with patch.object(door_collision.hkpackfile,'Packfile',return_value=SharedSystem()):result=door_collision.plan(source,rig)
        self.assertEqual(len(result['systems']),1)
        self.assertEqual([(a['node'],a['body_id']) for a in result['attachments']],[(1,0),(2,1)])
        self.assertTrue(all(a['follows_animated_ancestor'] for a in result['attachments']))
        self.assertEqual(result['unassigned_bodies'],[])
        self.assertFalse(result['geometry_converted'])
    def test_invalid_and_duplicate_body_ids_rejected(self):
        for body in [0,2]:
            source=self.source();source.blocks[-1]=struct.pack('<iHiI',2,128,6,body)
            with patch.object(door_collision.hkpackfile,'Packfile',return_value=SharedSystem()):
                with self.assertRaises(nif.NifError):door_collision.plan(source,door_rig.plan(source))
    def test_unassigned_body_reported_and_truncated_attachment_rejected(self):
        source=self.source();source.blocks.pop()
        with patch.object(door_collision.hkpackfile,'Packfile',return_value=SharedSystem()):
            result=door_collision.plan(source,door_rig.plan(source))
        self.assertEqual(result['unassigned_bodies'],[{'system_block':6,'body_id':1}])
        source.blocks[-1]=source.blocks[-1][:-4]
        with self.assertRaises(nif.NifError):door_collision.plan(source,door_rig.plan(source))

    def test_off_rig_collision_node_listed_under_its_moving_bone(self):
        source=fixture();data=source.add_block('bhkPhysicsSystem',struct.pack('<I',4)+b'test')
        rig0=door_rig.plan(source);leaf_bone=next(i for i,b in enumerate(rig0['bones']) if b['node']==1)
        leaf=bytearray(source.blocks[1]);count_at=len(leaf)-8;helper=len(source.blocks)
        source.blocks[1]=bytes(leaf[:count_at])+struct.pack('<Iii',2,3,helper)
        name=source.string_index(b'c_Deck');leaf[0:4]=struct.pack('<i',name)
        source.add_block('NiNode',bytes(leaf[:count_at])+struct.pack('<I',0))
        source.add_block('bhkNPCollisionObject',struct.pack('<iHiI',helper,128,data,0))
        with patch.object(door_collision.hkpackfile,'Packfile',return_value=SharedSystem()):
            result=door_collision.plan(source,rig0)
        one=result['attachments'][0]
        self.assertEqual((one['node'],one['bone'],one['off_rig']),(helper,leaf_bone,True))
        self.assertTrue(one['follows_animated_ancestor'])
    def test_collision_node_with_no_rig_ancestor_still_rejected(self):
        source=fixture();data=source.add_block('bhkPhysicsSystem',struct.pack('<I',4)+b'test')
        source.add_block('bhkNPCollisionObject',struct.pack('<iHiI',0,128,data,0))
        rig=door_rig.plan(source);rig['bones']=[b for b in rig['bones'] if b['node']!=0]
        with patch.object(door_collision.hkpackfile,'Packfile',return_value=SharedSystem()):
            with self.assertRaises(nif.NifError):door_collision.plan(source,rig)
