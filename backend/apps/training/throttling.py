from rest_framework.throttling import SimpleRateThrottle


class SessionFormationThrottle(SimpleRateThrottle):
    """Limite les appels à l'espace apprenant, par adresse.

    Le jeton fait 256 bits : le deviner n'est pas un scénario réaliste, et ce
    n'est pas ce que cette limite protège. Elle protège contre l'essai en
    masse de jetons — qui ne trouverait rien, mais coûterait une requête de
    base de données à chaque tentative.

    Le seuil est volontairement haut : une entreprise entière peut suivre le
    cours depuis une seule adresse publique (un bureau derrière une même
    sortie internet). Une limite serrée bloquerait les vrais salariés bien
    avant de gêner qui que ce soit d'autre.
    """

    scope = "formation_session"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}
