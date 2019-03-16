from msorm import utils

questions = ['Info om forældre/værge', 'Forælders/værges navn under kursusperioden:',
             'Forælders/værges telefonnummer under kursusperioden:', 'Forælders/værges mail under kursusperioden:',
             'Bekræft e-mail:', 'Info om leder', 'Leders navn under kursusperioden:',
             'Leders mail under kursusperioden: ', 'Leders telefonnummer under kursusperioden:', 'Info om spejderen',
             'Hvor mange år har du været spejder?', 'Hvilket år er du sidst blevet stivkrampevaccineret?',
             'Har du fysiske begrænsninger/sygdomme/diagnoser (fx dårlig ryg, knæ, astma, diabetes, autisme mm.) eller tager du medicin? Så beskriv det her:',
             'Har du nogle særlige kosthensyn (madallergi, vegetar mm.), så skriv dem her:', 'Anden info:',
             'Må kursusteamet dele dine kontaktoplysninger med andre kursusdeltagere for at hjælpe dig med at koordinere transport/samkørsel til og fra kurset?',
             'Sådan tilmelder du dig:', 'Vælg kurser:', 'Spejderven/-veninde:']


def test_cosine():
    assert utils.cosine_compare_to_list('Vælg kurser', questions, 0.8)[0] == 'Vælg kurser:'
