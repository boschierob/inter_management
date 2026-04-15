import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime
# On importe la logique de votre script principal
# (Assurez-vous que votre fichier principal se nomme 'main_script.py' ou adaptez le nom)
from generer_factures_qonto import generer_factures

class TestFacturationQonto(unittest.TestCase):

    @patch('generer_factures_qonto.requests.post')
    def test_groupement_interventions(self, mock_post):
        """Vérifie que le script additionne bien deux interventions pour le même client"""
        
        # 1. Simulation de la réponse de Notion (2 interventions pour le même client)
        mock_notion_response = MagicMock()
        mock_notion_response.json.return_value = {
            "results": [
                {   
                    "id": "page-id-1",
                    "properties": {
                        "ID Qonto (Rollup)": {"rollup": {"array": [{"rich_text": [{"plain_text": "id_client_A"}]}]}},
                        "Client": {"type": "title", "title": [{"plain_text": "Client A"}]},
                        "Date Intervention": {"date": {"start": "2024-05-01"}},
                        "Montant HT": {"number": 100.0}
                    }
                },
                {
                    "id": "page-id-2",
                    "properties": {
                        "ID Qonto (Rollup)": {"rollup": {"array": [{"rich_text": [{"plain_text": "id_client_A"}]}]}},
                        "Client": {"type": "title", "title": [{"plain_text": "Client A"}]},
                        "Date Intervention": {"date": {"start": "2024-05-15"}},
                        "Montant HT": {"number": 50.0}
                    }
                }
            ]
        }
        
        # On simule aussi la réponse de Qonto (201 Created)
        mock_qonto_response = MagicMock()
        mock_qonto_response.status_code = 201
        
        # Le premier appel sera Notion, le second sera Qonto
        mock_post.side_effect = [mock_notion_response, mock_qonto_response]

        # 2. Lancer la fonction
        with patch('generer_factures_qonto.get_interventions') as mock_get:
            mock_get.return_value = mock_notion_response.json()["results"]
            generer_factures()

        # 3. Vérification : Qonto a-t-il reçu 150.00 € (100 + 50) ?
        # On regarde le JSON envoyé à Qonto lors de l'appel POST
        called_payload = mock_post.call_args_list[-1][1]['json']
        montant_envoye = called_payload['items'][0]['unit_price']['value']
        
        self.assertEqual(montant_envoye, "150.00")
        print("\n✅ Test de groupement réussi : 100€ + 50€ = 150.00€")

    def test_date_format(self):
        """Vérifie que le formatage du mois/année est correct pour le titre"""
        date_test = "2024-05-22"
        mois_annee = datetime.strptime(date_test, "%Y-%m-%d").strftime("%m/%Y")
        self.assertEqual(mois_annee, "05/2024")
        print("✅ Test de formatage de date réussi")

if __name__ == '__main__':
    unittest.main()