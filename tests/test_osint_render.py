"""Meaningful local rendering/byte-binding adversarial checks; no network."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from adapters import osint_render as render

ROOT=Path(__file__).resolve().parents[1]


class OsintRenderChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import PIL, reportlab, svglib, fontTools
        except ImportError as error:
            raise unittest.SkipTest('HOLD_OPTIONAL_GRAPH_DEPENDENCY: '+str(error))
        builder=ROOT.parent/'builder'
        builder.mkdir(exist_ok=True)
        cls.work=Path(tempfile.mkdtemp(prefix='osint-checks-',dir=builder))
        cls.case_path=ROOT/'fixtures/osint_case.json'
        cls.case=json.loads(cls.case_path.read_bytes())
        cls.content=render.render_graph(cls.case_path,cls.work/'content')
        cls.report=render.make_report(cls.case_path,cls.work/'report')
        cls.history=render.history_graph(ROOT/'fixtures/osint_history_snapshot.json',cls.work/'history')

    def save_case(self,name,value):
        path=self.work/(name+'.json');path.write_bytes(render.canonical(value)+b'\n');return path

    def test_actual_native_render_formats_and_byte_bindings(self):
        self.assertEqual(self.content['state'],'PASS_PINNED_LOCAL_OSINT_RENDER')
        self.assertEqual(self.content['source_evidence_class'],'SYNTHETIC_FIXTURE')
        self.assertTrue(all(self.content['source_ids_visible_in_nodes'].values()))
        self.assertEqual(self.content['glyph_qa']['unsupported_glyphs'],[])
        for name,descriptor in self.content['files'].items():
            raw=(self.work/'content'/name).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),descriptor['sha256'])
            self.assertEqual(len(raw),descriptor['bytes'])
        self.assertEqual((self.work/'content/graph.png').read_bytes()[:8],b'\x89PNG\r\n\x1a\n')
        self.assertTrue((self.work/'content/graph.pdf').read_bytes().startswith(b'%PDF-'))
        for source in self.case['sources']:
            self.assertEqual((self.work/'content/sources'/(source['id']+'.txt')).read_bytes(),source['body_text'].encode('utf-8'))

    def test_repeated_native_graph_same_frozen_input_same_artifact_bytes(self):
        for name in ['graph.svg','graph.png','graph.pdf','graph_master.json']:
            self.assertEqual((self.work/'content'/name).read_bytes(),(self.work/'report/graph'/name).read_bytes(),name)

    def test_report_preserves_original_and_keeps_guard_review(self):
        self.assertEqual((self.work/'report/original_report.md').read_bytes(),self.case['report_markdown'].encode('utf-8'))
        self.assertEqual(len(self.report['five_line_initial_brief']),5)
        self.assertEqual(self.report['network_calls'],0)
        self.assertEqual(self.report['canonical_writes'],0)
        self.assertEqual(self.report['document_guard']['document_mutation'],'NONE')
        self.assertFalse(self.report['document_guard']['prose_correctness_certification'])
        self.assertIn(self.report['document_guard']['status'],{'REVIEW','PASS','UNKNOWN'})
        self.assertEqual((self.work/'report/Report.md').read_bytes(),(self.work/'report/report.md').read_bytes())
        self.assertEqual((self.work/'report/Report.pdf').read_bytes(),(self.work/'report/report.pdf').read_bytes())

    def test_bad_source_hash_rejected_before_output_creation(self):
        case=copy.deepcopy(self.case);case['sources'][0]['body_text']+='tamper'
        output=self.work/'bad-hash-output'
        with self.assertRaisesRegex(render.OsintRenderHold,'ORIGINAL_BYTE_SHA256_MISMATCH'):
            render.render_graph(self.save_case('bad-hash',case),output)
        self.assertFalse(output.exists())

    def test_source_identifier_cannot_escape_output(self):
        case=copy.deepcopy(self.case);case['sources'][0]['id']='C1/../../outside'
        output=self.work/'bad-id-output'
        with self.assertRaisesRegex(render.OsintRenderHold,'SOURCE_ID'):
            render.render_graph(self.save_case('bad-id',case),output)
        self.assertFalse(output.exists())

    def test_native_history_keeps_reference_not_causation(self):
        self.assertEqual(self.history['state'],'PASS_PINNED_LOCAL_OSINT_RENDER')
        self.assertEqual(self.history['source_evidence_class'],'SYNTHETIC_FIXTURE')
        self.assertTrue(all(self.history['source_ids_visible_in_nodes'].values()))
        master=json.loads((self.work/'history/graph_master.json').read_bytes())
        self.assertTrue(master['graph']['links'])
        for link in master['graph']['links']:
            self.assertEqual(link['relation'],'PERSISTED_CONTEXT_REFERENCE')
            self.assertEqual(link['causation'],'NOT_INFERRED')
        snapshot=json.loads((ROOT/'fixtures/osint_history_snapshot.json').read_bytes())
        snapshot['source_material'][0]['copy_sha256']='0'*64
        snapshot['snapshot_sha256']=render.sha(render.canonical({k:v for k,v in snapshot.items() if k!='snapshot_sha256'}))
        p=self.save_case('tampered-history',snapshot)
        with self.assertRaisesRegex(ValueError,'SOURCE_MISMATCH'):
            render.history_graph(p,self.work/'tampered-history-output')

    def test_source_manifest_cannot_self_approve_new_bytes(self):
        copied=self.work/'forged-runtime';copied.mkdir()
        (copied/'SOURCE_PROVENANCE.json').write_text('{"source_files":[]}\n',encoding='utf-8')
        with patch.object(render,'RUNTIME',copied):
            with self.assertRaisesRegex(render.OsintRenderHold,'PROVENANCE_ANCHOR'):
                render._native()

    def test_projection_types_preserve_original_json_and_label_derived_md(self):
        source=ROOT/'fixtures/workledger_projection_fixture.json'
        result=render.render_graph(source,self.work/'workledger','workledger')
        self.assertEqual(result['state'],'PASS_PINNED_LOCAL_OSINT_RENDER')
        self.assertEqual(result['graph_type'],'workledger')
        self.assertEqual((self.work/'workledger/original_input.json').read_bytes(),source.read_bytes())
        self.assertEqual((self.work/'workledger/sources/C1.txt').read_bytes(),source.read_bytes())
        self.assertFalse(result['source_document']['state_machine_reconstructed'])
        self.assertEqual(result['source_document']['ORIGINAL_JSON_BYTE_SHA256'],render.sha(source.read_bytes()))
        source=ROOT/'fixtures/security_receipt_fixture.json'
        result=render.make_report(source,self.work/'security-report')
        self.assertEqual(result['state'],'PASS_PINNED_LOCAL_REPORT_AND_GRAPH')
        self.assertIsNone(result['ORIGINAL_MD_BYTE_SHA256'])
        self.assertEqual(result['renderer_md_origin'],'DERIVED_FROM_ORIGINAL_JSON_NOT_ORIGINAL_TARGET_SOURCE_MD')
        self.assertEqual((self.work/'security-report/original_input.json').read_bytes(),source.read_bytes())
        self.assertEqual(result['new_provider_calls'],0)
        self.assertEqual(result['canonical_writes'],0)
        with self.assertRaisesRegex(render.OsintRenderHold,'TYPED_JSON_PROJECTION_REQUIRED'):
            render.render_graph(self.case_path,self.work/'wrong-projection','security')


if __name__=='__main__':
    unittest.main(verbosity=2)
