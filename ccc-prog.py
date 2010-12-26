#!/usr/bin/env python

#
# Utility to write the cards
#
#
# Copyright (C) 2009  Sylvain Munaut <tnt@246tNt.com>
# Copyright (C) 2010  Harald Welte <laforge@gnumonks.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from optparse import OptionParser

from pySim.commands import SimCardCommands
from pySim.cards import _cards_classes

from ccc import StateManager, CardParameters



def csv_load_cards(filename):
	import csv
	fh = open(filename, 'r')
	cr = csv.reader(fh)
	cards = dict([(int(x[0]), CardParameters(int(x[0]), x[1], x[2], x[3])) for x in cr])
	fh.close()
	return cards


def card_detect(opts, scc):

	# Detect type if needed
	card = None
	ctypes = dict([(kls.name, kls) for kls in _cards_classes])

	if opts.type in ("auto", "auto_once"):
		for kls in _cards_classes:
			card = kls.autodetect(scc)
			if card:
				print "Autodetected card type %s" % card.name
				card.reset()
				break

		if card is None:
			print "Autodetection failed"
			return

		if opts.type == "auto_once":
			opts.type = card.name

	elif opts.type in ctypes:
		card = ctypes[opts.type](scc)

	else:
		raise ValueError("Unknown card type %s" % opts.type)

	return card


def print_parameters(params):

	print """Generated card parameters :
 > Name    : %(name)s
 > SMSP    : %(smsp)s
 > ICCID   : %(iccid)s
 > MCC/MNC : %(mcc)d/%(mnc)d
 > IMSI    : %(imsi)s
 > Ki      : %(ki)s
"""	% params


#
# Main
#

def parse_options():

	parser = OptionParser(usage="usage: %prog [options]")

	# Card interface
	parser.add_option("-d", "--device", dest="device", metavar="DEV",
			help="Serial Device for SIM access [default: %default]",
			default="/dev/ttyUSB0",
		)
	parser.add_option("-b", "--baud", dest="baudrate", type="int", metavar="BAUD",
			help="Baudrate used for SIM access [default: %default]",
			default=9600,
		)
	parser.add_option("-p", "--pcsc-device", dest="pcsc_dev", type='int', metavar="PCSC",
			help="Which PC/SC reader number for SIM access",
			default=None,
		)
	parser.add_option("-t", "--type", dest="type",
			help="Card type (user -t list to view) [default: %default]",
			default="auto",
		)
	parser.add_option("-e", "--erase", dest="erase", action='store_true',
			help="Erase beforehand [default: %default]",
			default=False,
		)

	# Data source
	parser.add_option("--state", dest="state_file", metavar="FILE",
			help="Use this state file",
			)
	parser.add_option("--read-csv", dest="read_csv", metavar="FILE",
			help="Read parameters from CSV file",
		)

	(options, args) = parser.parse_args()

	if options.type == 'list':
		for kls in _cards_classes:
			print kls.name
		sys.exit(0)

	if args:
		parser.error("Extraneous arguments")

	return options


def main():

	# Parse options
	opts = parse_options()

	# Connect to the card
	if opts.pcsc_dev is None:
		from pySim.transport.serial import SerialSimLink
		sl = SerialSimLink(device=opts.device, baudrate=opts.baudrate)
	else:
		from pySim.transport.pcsc import PcscSimLink
		sl = PcscSimLink(opts.pcsc_dev)

	# Create command layer
	scc = SimCardCommands(transport=sl)

	# Load state
	sm = StateManager(opts.state_file)
	sm.load()

	np = sm.network

	# Load cards
	cards = csv_load_cards(opts.read_csv)

	# Iterate
	done = False
	first = True
	card = None

	while not done:
		# Connect transport
		print "Insert card now (or CTRL-C to cancel)"
		sl.wait_for_card(newcardonly=not first)

		# Not the first anymore !
		first = False

		# Get card
		card = card_detect(opts, scc)
		if card is None:
			if opts.batch_mode:
				first = False
				continue
			else:
				sys.exit(-1)

		# Erase if requested
		if opts.erase:
			print "Formatting ..."
			card.erase()
			card.reset()

		# Get parameters
		cp = cards[sm.next_write_num()]
		cpp = {
			'name': np.name,
			'smsp': np.smsp,
			'iccid': cp.iccid,
			'mcc': np.mcc,
			'mnc': np.mnc,
			'imsi': cp.imsi,
			'ki': cp.ki,
		}
		print_parameters(cpp)

		# Program the card
		print "Programming ..."
		card.program(cpp)

		# Update state
		sm.save()

		# Done for this card and maybe for everything ?
		print "Card written !\n"


if __name__ == '__main__':
	main()
