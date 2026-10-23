"""paraGUI contention task pgm3trip (pair m3, family F2: one Thunderbird); see spec_m3.md."""
from __future__ import annotations

from typing import TYPE_CHECKING

from desktop_env.task_base import BaseTask
from evaluation_examples.task_class import pg_m3 as pair

if TYPE_CHECKING:
    from desktop_env.controllers.setup import SetupController
    from desktop_env.desktop_env import DesktopEnv


class TaskPgm3trip(BaseTask):
    intermediate_eval_safe = False
    id = "pgm3trip"
    snapshot = "paragui"
    instruction = "In December I travel to Vienna (client workshop at Donauwerke) and on to Copenhagen (NordData Summit); all the booking confirmations are in my Thunderbird mailbox (lukas.brandt@aldervane.de). Please: 1) save the train e-ticket, the Austrian Airlines itinerary and the Copenhagen hotel confirmation PDFs into ~/Documents/Travel/; 2) write an itinerary document ~/Documents/Travel/Itinerary_Dec2026.docx that lists everything in chronological order - each journey with date, departure and arrival time and booking reference, each hotel with check-in and check-out dates and confirmation number, the two workshop sessions and the conference days; 3) add the train ride and both flights to my Thunderbird calendar, each from departure to arrival time with the booking reference in the event, plus the NordData Summit as an all-day event covering its two days; 4) reply to the travel desk's pre-approval request with the total cost of transport and hotels, and save the reply as a draft. If a booking was changed later, use the latest information; use the local times printed on the bookings."
    source = "paragui"
    trajectory = "trajectories/"
    related_apps = ['thunderbird', 'libreoffice_writer']
    proxy = False
    fixed_ip = False
    possibility_of_env_change = "low"

    def setup(self, setup_controller: "SetupController", use_proxy: bool = False) -> None:
        pair.setup(setup_controller)

    def evaluate(self, env: "DesktopEnv"):
        return pair.evaluate_trip(env, "pgm3trip_result")


TASK_CLASS = TaskPgm3trip
