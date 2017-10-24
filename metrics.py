import itertools
from collections import defaultdict, Counter
import pandas as pd


class CalculateMetrics(object):
    def __init__(self, league_id, config):
        self.league_id = league_id
        self.config = config

    @staticmethod
    def get_standings(league_standings_data):
        current_standings_data = []
        for team in league_standings_data[0].get("standings").get("teams").get("team"):
            streak_type = team.get("team_standings").get("streak").get("type")
            if streak_type == "loss":
                streak_type = "L"
            elif streak_type == "win":
                streak_type = "W"
            else:
                streak_type = "T"

            current_standings_data.append([
                team.get("team_standings").get("rank"),
                team.get("name"),
                team.get("managers").get("manager").get("nickname"),
                team.get("team_standings").get("outcome_totals").get("wins") + "-" +
                team.get("team_standings").get("outcome_totals").get("losses") + "-" +
                team.get("team_standings").get("outcome_totals").get("ties") + " (" +
                team.get("team_standings").get("outcome_totals").get("percentage") + ")",
                team.get("team_standings").get("points_for"),
                team.get("team_standings").get("points_against"),
                streak_type + "-" + team.get("team_standings").get("streak").get("value"),
                team.get("waiver_priority"),
                team.get("number_of_moves"),
                team.get("number_of_trades")
            ])
        return current_standings_data

    @staticmethod
    def get_score_data(score_results):
        score_results_data = []
        place = 1
        for key, value in score_results:
            ranked_team_name = key
            ranked_team_manager = value.get("manager")
            ranked_weekly_score = "%.2f" % float(value.get("score"))
            ranked_weekly_bench_score = "%.2f" % float(value.get("bench_score"))

            score_results_data.append(
                [place, ranked_team_name, ranked_team_manager, ranked_weekly_score, ranked_weekly_bench_score])

            place += 1

        return score_results_data

    @staticmethod
    def get_coaching_efficiency_data(coaching_efficiency_results, efficiency_dq_count):
        coaching_efficiency_results_data = []
        place = 1
        for key, value in coaching_efficiency_results:
            ranked_team_name = key
            ranked_team_manager = value.get("manager")
            ranked_coaching_efficiency = value.get("coaching_efficiency")

            if ranked_coaching_efficiency == 0.0:
                ranked_coaching_efficiency = "DQ"
                efficiency_dq_count += 1
            else:
                ranked_coaching_efficiency = "%.2f%%" % float(ranked_coaching_efficiency)

            coaching_efficiency_results_data.append(
                [place, ranked_team_name, ranked_team_manager, ranked_coaching_efficiency])

            place += 1

        return coaching_efficiency_results_data

    @staticmethod
    def get_luck_data(luck_results):
        luck_results_data = []
        place = 1
        for key, value in luck_results:
            ranked_team_name = key
            ranked_team_manager = value.get("manager")
            ranked_luck = "%.2f%%" % value.get("luck")

            luck_results_data.append([place, ranked_team_name, ranked_team_manager, ranked_luck])

            place += 1
        return luck_results_data

    def get_num_ties(self, results, results_data, week, tie_type):

        if tie_type != "power_rank":
            num_ties = sum(manager.count(results_data[0][3]) for manager in results_data) - 1
        else:
            num_ties = sum(manager.count(results_data[0][0]) for manager in results_data) - 1
        newline = ""
        if tie_type == "luck":
            newline = "\n"

        # if there are ties, record them and break them if possible
        if num_ties > 0:
            print("THERE IS A %s TIE IN WEEK %s!%s" % (tie_type.replace("_", " ").upper(), week, newline))
            ties_list = list(results[:num_ties + 1])

            count = num_ties
            index = 0
            while (count + 1) > 0:
                if self.league_id == self.config.get("Fantasy_Football_Report_Settings", "league_of_emperors_id") and tie_type == "score":
                    place = index + 1
                else:
                    place = "1*"
                results_data[index] = [
                    place,
                    ties_list[index][0],
                    ties_list[index][1].get("manager"),
                    ties_list[index][1].get(tie_type)
                ]
                if tie_type == "score":
                    results_data[index].append(ties_list[index][1].get("bench_score"))
                count -= 1
                index += 1
        else:
            print("No %s ties in week %s.%s" % (tie_type.replace("_", " "), week, newline))

        return num_ties

    def resolve_score_ties(self, score_results_data):

        groups = [list(group) for key, group in itertools.groupby(score_results_data, lambda x: x[3])]

        resolved_score_results_data = []
        place = 1
        for group in groups:
            for team in sorted(group, key=lambda x: x[-1], reverse=True):
                if groups.index(group) != 0:
                    team[0] = place
                else:
                    if self.league_id == self.config.get("Fantasy_Football_Report_Settings", "league_of_emperors_id"):
                        team[0] = place
                resolved_score_results_data.append(team)
                place += 1

        return resolved_score_results_data


class CoachingEfficiency(object):
    # prohibited statuses to check team coaching efficiency eligibility
    prohibited_status_list = ["PUP-P", "SUSP", "O", "IR"]

    def __init__(self, roster_settings):
        self.roster_slots = roster_settings["slots"]

        self.flex_positions = {
            "FLEX": roster_settings["flex_positions"],
            "D": ["D", "DB", "DL", "LB", "DT", "DE", "S", "CB"]
        }

    def get_eligible_positions(self, player):
        eligible = []

        for position in self.roster_slots:
            if position in player["eligible_positions"]:
                # special case, because all defensive players get D as an eligible position
                # whereas for offense, there is no special eligible position for FLEX
                if position != "D":
                    eligible.append(position)

                # assign all flex positions the player is eligible for
                for flex_position, base_positions in self.flex_positions.items():
                    if position in base_positions:
                        eligible.append(flex_position)

        return eligible

    def get_optimal_players(self, eligible_players, position):
        player_list = eligible_players[position]

        num_slots = self.roster_slots[position]

        return sorted(player_list, key=lambda x: x["fantasy_points"], reverse=True)[:num_slots]

    def get_optimal_flex(self, eligible_positions, optimal):

        # method to turn player dict into a tuple for use in sets/comparison
        # should just have a class, but w/e
        def create_tuple(player_info):
            return (
                player_info["name"],
                player_info["fantasy_points"]
            )

        for flex_position, base_positions in self.flex_positions.items():
            candidates = set([create_tuple(player) for player in eligible_positions[flex_position]])

            optimal_allocated = set()
            # go through positions that makeup the flex position
            # and add each player from the optimal list to an allocated set
            for base_position in base_positions:
                for player in optimal.get(base_position, []):
                    optimal_allocated.add(create_tuple(player))

            # extract already allocated players from candidates
            available = candidates - optimal_allocated

            num_slots = self.roster_slots[flex_position]

            # convert back to list, sort, take as many as there are slots available
            optimal_flex = sorted(list(available), key=lambda x: x[1], reverse=True)[:num_slots]

            # grab the player dict that matches and return those
            # so that the data types we deal with are all similar
            for player in eligible_positions[flex_position]:
                for optimal_flex_player in optimal_flex:
                    if create_tuple(player) == optimal_flex_player:
                        yield player

    def is_player_eligible(self, player, week):
        return player["status"] in self.prohibited_status_list or player["bye_week"] == week

    def execute_coaching_efficiency(self, team_name, team_info, week, league_roster_active_slots,
                                    disqualification_eligible=False):

        players = team_info["players"]

        eligible_positions = defaultdict(list)

        for player in players:
            for position in self.get_eligible_positions(player):
                eligible_positions[position].append(player)

        # debug stuff
        # import json
        # for position, players in eligible_positions.items():
        #     print("{0}: {1}".format(position, [p["name"] for p in players]))

        optimal_players = []
        optimal = {}

        for position in self.roster_slots:
            if position in self.flex_positions.keys():
                # handle flex positions later...
                continue
            optimal_position = self.get_optimal_players(eligible_positions, position)
            optimal_players.append(optimal_position)
            optimal[position] = optimal_position

        # now that we have optimal by position, figure out flex positions
        optimal_flexes = list(self.get_optimal_flex(eligible_positions, optimal))

        optimal_players.append(optimal_flexes)

        optimal_lineup = [item for sublist in optimal_players for item in sublist]

        # calculate optimal score
        optimal_score = sum([x["fantasy_points"] for x in optimal_lineup])

        # print("optimal lineup for " + team_name)
        # for player in optimal_lineup:
        #     print(player)

        # calculate coaching efficiency
        actual_weekly_score = team_info["score"]

        coaching_efficiency = (actual_weekly_score / optimal_score) * 100

        # apply coaching efficiency eligibility requirements for League of Emperors
        if disqualification_eligible:

            bench_players = [p for p in players if p["selected_position"] == "BN"]
            ineligible_efficiency_player_count = len([p for p in bench_players if self.is_player_eligible(p, week)])
            positions_filled_active = team_info["positions_filled_active"]

            if Counter(league_roster_active_slots) == Counter(positions_filled_active):
                if ineligible_efficiency_player_count <= 4:
                    efficiency_disqualification = False
                else:
                    print("ROSTER INVALID! There are %d inactive players on the bench of %s in week %s!" % (
                        ineligible_efficiency_player_count, team_name, week))
                    efficiency_disqualification = True

            else:
                print(
                    "ROSTER INVALID! There is not a full squad of active players starting on %s in week %s!" % (
                        team_name,
                        week))
                efficiency_disqualification = True

            if efficiency_disqualification:
                coaching_efficiency = 0.0

        return coaching_efficiency


class Breakdown(object):
    def __init__(self):
        pass

    def execute_breakdown(self, teams, matchups_list):

        result = defaultdict(dict)
        matchups = {name: value["result"] for pair in matchups_list for name, value in pair.items()}

        for team_name, team in teams.items():
            record = {
                "W": 0,
                "L": 0,
                "T": 0
            }

            for team_name2, team2 in teams.items():
                if team["team_id"] == team2["team_id"]:
                    continue
                score1 = team["score"]
                score2 = team2["score"]
                if score1 > score2:
                    record["W"] += 1
                elif score1 < score2:
                    record["L"] += 1
                else:
                    record["T"] += 1

            result[team_name]["breakdown"] = record

            # calc luck %
            # TODO: assuming no ties...  how are tiebreakers handled?
            luck = 0.0
            # number of teams excluding current team
            num_teams = float(len(teams.keys())) - 1

            if record["W"] != 0 and record["L"] != 0:
                matchup_result = matchups[team_name]
                if matchup_result == "W" or matchup_result == "T":
                    luck = (record["L"] + record["T"]) / num_teams
                else:
                    luck = 0 - (record["W"] + record["T"]) / num_teams

            result[team_name]["luck"] = luck

        for team in teams:
            # "%.2f%%" % luck
            teams[team]["luck"] = result[team]["luck"] * 100
            teams[team]["breakdown"] = result[team]["breakdown"]
            teams[team]["matchup_result"] = result[team]

        return result


class SeasonAverageCalculator(object):
    def __init__(self, team_names, report_info_dict):
        self.team_names = team_names
        self.report_info_dict = report_info_dict

    def get_average(self, data, key, with_percent_bool, bench_column_bool=True, reverse_bool=True):
        """
        append parameter is hack to support bench scoring for a specific use case
        TODO: dont do that
        """

        season_average_list = []
        team_index = 0
        for team in data:
            team_name = self.team_names[team_index]
            season_average_value = "{0:.2f}".format(sum([float(week[1]) for week in team]) / float(len(team)))
            season_average_list.append([team_name, season_average_value])
            team_index += 1
        ordered_average_values = sorted(season_average_list, key=lambda x: float(x[1]), reverse=reverse_bool)
        for team in ordered_average_values:
            ordered_average_values[ordered_average_values.index(team)] = [ordered_average_values.index(team), team[0],
                                                                          team[1]]

        ordered_season_average_list = []
        for ordered_team in self.report_info_dict.get(key):
            for team in ordered_average_values:
                if ordered_team[1] == team[1]:
                    if with_percent_bool:
                        ordered_team[3] = "{0:.2f}%".format(float(str(ordered_team[3]).replace("%", "")))
                        ordered_team.append(str(team[2]) + "% (" + str(ordered_average_values.index(team) + 1) + ")")
                    elif bench_column_bool:
                        ordered_team[3] = "{0:.2f}".format(float(str(ordered_team[3])))
                        ordered_team.insert(-1, str(team[2]) + " (" + str(ordered_average_values.index(team) + 1) + ")")
                    else:
                        value = "{0} ({1})".format(str(team[2]), str(ordered_average_values.index(team) + 1))
                        ordered_team.append(value)

                    ordered_season_average_list.append(ordered_team)
        return ordered_season_average_list


class PointsByPosition(object):
    def __init__(self, roster_settings):

        self.roster_slots = roster_settings.get("slots")
        self.flex_positions = {
            "FLEX": roster_settings["flex_positions"],
            "D": ["D", "DB", "DL", "LB", "DT", "DE", "S", "CB"]
        }

    @staticmethod
    def get_starting_players(players):
        return [p for p in players if p["selected_position"] != "BN"]

    @staticmethod
    def get_points_for_position(players, position):
        total_points_by_position = 0
        for player in players:
            player_positions = player["eligible_positions"]
            if not isinstance(player_positions, list):
                player_positions = [player_positions]
            if position in player_positions and player["selected_position"] != "BN":
                total_points_by_position += float(player["fantasy_points"])

        return total_points_by_position

    @staticmethod
    def calculate_points_by_position_season_averages(season_average_points_by_position_dict, report_info_dict):

        for team in season_average_points_by_position_dict.keys():
            points_by_position = season_average_points_by_position_dict.get(team)
            season_average_points_by_position = {}
            for week in points_by_position:
                for position in week:
                    position_points = season_average_points_by_position.get(position[0])
                    if position_points:
                        season_average_points_by_position[position[0]] = position_points + position[1]
                    else:
                        season_average_points_by_position[position[0]] = position[1]
            season_average_points_by_position_list = []
            for position in season_average_points_by_position.keys():
                season_average_points_by_position_list.append(
                    [position, season_average_points_by_position.get(position) / len(points_by_position)])
            season_average_points_by_position_list = sorted(season_average_points_by_position_list, key=lambda x: x[0])
            season_average_points_by_position_dict[team] = season_average_points_by_position_list

        report_info_dict["season_average_points_by_position"] = season_average_points_by_position_dict

    def execute_points_by_position(self, team_info):

        players = team_info["players"]

        player_points_by_position = []
        starting_players = self.get_starting_players(players)
        for slot in self.roster_slots.keys():
            if slot != "BN" and slot != "FLEX":
                player_points_by_position.append([slot, self.get_points_for_position(starting_players, slot)])

        player_points_by_position = sorted(player_points_by_position, key=lambda x: x[0])
        return player_points_by_position

    def get_weekly_points_by_position(self, league_id, config, week, roster, active_slots, team_results_dict):

        coaching_efficiency = CoachingEfficiency(roster)
        weekly_points_by_position_data = []
        for team_name, team_info in team_results_dict.items():
            disqualification_eligible = league_id == config.get("Fantasy_Football_Report_Settings",
                                                                "league_of_emperors_id")
            team_info["coaching_efficiency"] = coaching_efficiency.execute_coaching_efficiency(team_name, team_info,
                                                                                               int(week),
                                                                                               active_slots,
                                                                                               disqualification_eligible=disqualification_eligible)
            for slot in roster["slots"].keys():
                if roster["slots"].get(slot) == 0:
                    del roster["slots"][slot]
            player_points_by_position = self.execute_points_by_position(team_info)
            weekly_points_by_position_data.append([team_name, player_points_by_position])

        # Option to disqualify chosen team for current week of coaching efficiency
        if week == config.get("Fantasy_Football_Report_Settings", "chosen_week"):
            disqualified_team = config.get("Fantasy_Football_Report_Settings",
                                           "coaching_efficiency_disqualified_team")
            if disqualified_team:
                team_results_dict.get(disqualified_team)["coaching_efficiency"] = "0.0%"

        return weekly_points_by_position_data


class PowerRanking(object):

    def __init__(self):
        pass

    @staticmethod
    def power_ranking(row):
        result = (row["score_rank"] + row["coach_rank"] + row["luck_rank"]) / 3.0

        return result

    def execute_power_ranking(self, teams):
        """
        avg of (weekly points rank + weekly overall win rank)
        """

        teams = [teams[key] for key in teams]

        df = pd.DataFrame.from_dict(teams)

        df["score_rank"] = df["score"].rank(ascending=False)
        df["coach_rank"] = df["coaching_efficiency"].rank(ascending=False)
        df["luck_rank"] = df["luck"].rank(ascending=False)
        df["power_rank"] = df.apply(self.power_ranking, axis=1).rank()

        # convert to just return calculated results
        # TODO: this is probably not the best way?

        teams = df.to_dict(orient="records")

        results = {}

        for team in teams:
            results[team["name"]] = {
                "score_rank": team["score_rank"],
                "coach_rank": team["coach_rank"],
                "luck_rank": team["luck_rank"],
                "power_rank": team["power_rank"]
            }

        return results