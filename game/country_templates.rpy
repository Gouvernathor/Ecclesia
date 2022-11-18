init python:
    from collections import namedtuple

define country_template = namedtuple('country_template', ("name", "houses", "executive", "parties"), defaults=(None,))

label country_templates:
    $ renpy.dynamic("_name", country_templates=[])
    python hide:
        congress = (actors.House("House of Representatives", 435,
                          election_period=24),
                    actors.House("Senate", 100,
                          election_period=72,
                          majority=.6))
        applyelec(congress[0], 1, voting_method.SingleVote, attribution_method.Plurality)
        applyelec(congress[1], 2, voting_method.SingleVote, attribution_method.Plurality)
        commons = (actors.House("House of Commons", 650,
                         election_period=60),)
        applyelec(commons[0], 1, voting_method.SingleVote, attribution_method.Plurality)
        parlement = (actors.House("National Assembly", 577,
                                  election_period=60),
                     actors.House("Senate", 348,
                                  election_period=72))
        applyelec(parlement[0], 1, voting_method.SingleVote, attribution_method.Plurality)
        parlement[1].circos = []
        for nb in (3, 3, 2, 1, 1, 5, 2, 2, 1, 2, 2, 2, 8, 3, 2, 2, 3, 2, 2, 1, 1, 3, 3, 2,
                   2, 3, 3, 3, 3, 4, 3, 5, 2, 6, 4, 4, 2, 3, 5, 2, 2, 2, 4, 2, 5, 3, 2, 2,
                   1, 4, 3, 3, 2, 2, 4, 2, 3, 5, 2, 11, 4, 2, 7, 3, 3, 2, 2, 5, 4, 7, 2, 3,
                   3, 2, 3, 12, 6, 6, 6, 2, 3, 2, 2, 4, 3, 3, 2, 2, 2, 2, 1, 5, 7, 6, 6, 5,
                   3, 2, 2, 4, 2, 2, 2, 1, 1, 1, 1, 12):
            if nb < 3:
                parlement[1].circos.append([nb,
                                            election_method.ElectionMethod(voting_method.SingleVote(),
                                                                           attribution_method.Plurality(nseats=nb)),
                                            []])
            else:
                parlement[1].circos.append([nb,
                                            election_method.ElectionMethod(voting_method.SingleVote(),
                                                                           attribution_method.HighestAverages(nseats=nb)),
                                            []])
        us_president = actors.Executive(origin="people",
                                        vetopower=True,
                                        vetoverride=congress,
                                        election_period=48,
                                        name="President",
                                        nseats=1)
        us_president.circos = []
        for nb, mult in ((54, 1), (40, 1), (30, 1), (28, 1), (19, 2), (17, 1), (16, 2),
                         (15, 1), (14, 1), (13, 1), (12, 1), (11, 4), (10, 5), (9, 2),
                         (8, 3), (7, 2), (6, 6), (5, 2), (4, 7), (3, 7)):
            # electors per states, and their multiplicity, following the 2020 census
            # nebraska and maine's alternate election system is ignored, because the classes don't support it
            for _k in range(mult):
                us_president.circos.append([nb,
                                            election_method.ElectionMethod(voting_method.SingleVote(),
                                                                           attribution_method.Plurality(nseats=nb)),
                                            []])

        country_templates.extend([
            country_template("United States",
                             congress,
                             us_president,
                             (actors.Party("Republican Party", color="#f00"),
                              actors.Party("Democratic Party", color="#00f"))),
            country_template("France (Vth Republic)",
                             parlement,
                             actors.Executive(origin="people",
                                       vetopower=False,
                                       election_period=48,
                                       name="President",
                                       nseats=1),
                             ),
            country_template("United Kingdom",
                             commons,
                             actors.Executive(origin=commons,
                                       vetopower=False,
                                       name="Prime Minister",
                                       nseats=1),
                             ),
        ])

        for c in country_templates:
            if (c.executive.origin == "people") and not (c.executive.circos[0][-1]):
                applyelec(c.executive, c.executive.seats, voting_method.SingleVote, attribution_method.Plurality)

        country_templates.sort(key=lambda x: x.name)
    "Templates loaded successfully."
    $ _name, houses[:], executive, parties = renpy.display_menu([(x.name, x) for x in country_templates])
    if _name in ("United States", "France (Vth Republic)"):
        "The current implementation doesn't support the mixed-size electoral districting required for the US president and the french Senate."
        jump country_templates
    pause
    $ populate(minncitizen())
    if parties is None:
        $ partis = actors.Party.generate(10)
    return
