import unittest
import requests_mock
import requests

from app.adsb.datasource.modesmixer import ModeSMixer


class ModeSMixerTest(unittest.TestCase):

    def _create_valid_reponse(self):
        return {
            'stats': {
                'epoch': '1234',
                'flights': ['A','B','C']
            }
        }

    def setUp(self):
        self.sut = ModeSMixer('mock://test.org')
        self.adapter = requests_mock.Adapter()
        self.sut.session.mount('mock', self.adapter)

    def test_valid_response(self):
        self.adapter.register_uri('POST', 'mock://test.org/json', json=self._create_valid_reponse())
        flight_results = self.sut.get_flight_info()
        self.assertCountEqual(flight_results, ['A','B','C'])


    def test_bad_base_url(self):
        self.adapter.register_uri('POST', 'mock://test.org/json', status_code=404)
        flight_results = self.sut.get_flight_info()
        self.assertEqual(flight_results, None)