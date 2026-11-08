"""AP16.03: precision wheel deltas and exact catalog filter confirmation."""
import copy
import json
from pathlib import Path
import unittest

from compact_widgets import scroll_wheel
from moviepilot_lists import BASE, ExportError, download_list, validate_catalog_filters


class ScrollTarget:
    def __init__(self):self.calls=[]
    def yview_scroll(self,*args):self.calls.append(args)


class CompletionTests(unittest.TestCase):
    def test_precision_deltas_accumulate_per_target_without_double_scroll(self):
        outer,inner=ScrollTarget(),ScrollTarget()
        for _ in range(3):self.assertEqual(scroll_wheel(outer,-30),'break')
        self.assertEqual(outer.calls,[])
        scroll_wheel(inner,-30);scroll_wheel(outer,-30)
        self.assertEqual(outer.calls,[(1,'units')]);self.assertEqual(inner.calls,[])
        for _ in range(3):scroll_wheel(inner,-30)
        self.assertEqual(inner.calls,[(1,'units')])
        scroll_wheel(inner,240);self.assertEqual(inner.calls[-1],(-2,'units'))
        scroll_wheel(outer,-60);scroll_wheel(outer,60);scroll_wheel(outer,60)
        self.assertEqual(outer.calls[-1],(-1,'units'))

    def test_catalog_filter_sets_must_exactly_match_requested_path(self):
        validate_catalog_filters(BASE+'/filme/beste',[])
        validate_catalog_filters(BASE+'/filme/beste/online-netflix',['online-netflix'])
        validate_catalog_filters(BASE+'/filme/beste/online-disney-plus/genre-drama',['genre-drama','online-disney-plus'])
        for returned in (None,[],['online-disney-plus'],['online-netflix','jahr-1994'],['online-netflix','online-netflix'],[{}]):
            with self.subTest(returned=returned),self.assertRaises(ExportError):
                validate_catalog_filters(BASE+'/filme/beste/online-netflix',returned)
        with self.assertRaises(ExportError):validate_catalog_filters(BASE+'/filme/beste',['online-netflix'])

    def test_real_disney_shape_rejected_for_netflix_without_changing_ratings(self):
        fixtures=json.loads((Path(__file__).parent/'fixtures/ap1602_public_pages.json').read_text(encoding='utf-8'))
        props=copy.deepcopy(fixtures['best']);props.update(total=25,filters=['online-disney-plus'])
        with self.assertRaisesRegex(ExportError,'Katalogfilter'):
            download_list(BASE+'/filme/beste/online-netflix',fetch=lambda _:props)
        result=download_list(BASE+'/filme/beste/online-disney-plus',fetch=lambda _:props)
        self.assertEqual(len(result.entries),25)
        self.assertAlmostEqual(result.entries[0]['community_rating'],8.44636)
