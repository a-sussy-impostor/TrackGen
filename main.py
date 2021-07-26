from PIL import Image
from PIL import ImageDraw

from flask import abort
from flask import Flask
from flask import request
from flask import send_file
from flask import render_template


Image.MAX_IMAGE_PIXELS = None
map_small = Image.open("map-small.jpg")
map_medium = Image.open("map-medium.jpg")


def get_hurdat_stage(initials):
	initials = initials.upper()
	if initials in ["TD", "TS", "HU"]: return "Tropical Cyclone"
	elif initials in ["SD", "SS"]: return "Subtropical Cyclone"
	elif initials in["EX", "LO", "DB", "WV"]: return "Extratropical Cyclone"


def get_atcf_stage(initials):
	initials = initials.upper()
	if initials in ["TY", "TD", "TS", "ST", "TC", "HU", "XX"]: return "Tropical Cyclone"
	elif initials in ["SD", "SS"]: return "Subtropical Cyclone"
	elif initials in ["EX", "MD", "IN", "DS", "LO", "WV", "ET", "DB"]: return "Extratropical Cyclone"


def get_ibtracs_stage(initials):
	initials = initials.upper()
	if initials in ["TS", "NR", "MX"]: return "Tropical Cyclone"
	elif initials == "SS": return "Subtropical Cyclone"
	elif initials in ["ET", "DS"]: return "Extratropical Cyclone"


def get_rsmc_stage(num):
	if num in ["2", "3", "4", "9"]: return "Tropical Cyclone"
	elif num in ["5", "7"]: return "Subtropical Cyclone"
	elif num == "6": return "Extratropical Cyclone"


def sshs_to_speed(num):
	if num == "-5": return 0
	elif num in["-4", "-3", "-1"]: return 34
	elif num in ["-2", "0"]: return 64
	elif num == "1": return 83
	elif num == "2": return 96
	elif num == "3": return 113
	elif num == "4": return 137
	elif num == "5": return 138
	else: return 0

def get_shape(stage):
	return {
		"extratropical cyclone": "triangle",
		"subtropical cyclone": "square",
		"tropical cyclone": "circle"
	}[stage.lower()]

def get_colour(speed):
	if speed == 0: return (192, 192, 192)
	elif speed <= 34: return (94, 186, 255)
	elif speed <= 64: return (0, 250, 244)
	elif speed <= 83: return (255, 255, 204)
	elif speed <= 96: return (255, 231, 117)
	elif speed <= 113: return (255, 193, 64)
	elif speed <= 137: return (255, 143, 32)
	else: return (255, 96, 96)


def make_map(tracks, size):
	if size == "medium": map, DOT_SIZE = map_medium, 30
	else: map, DOT_SIZE = map_small, 10

	FULL_WIDTH, FULL_HEIGHT = map.size


	for i in tracks:
		i["longitude"] = FULL_WIDTH/2 - float(i["longitude"][:-1]) * (-1 if i["longitude"][-1] == "E" else 1) / 360 * FULL_WIDTH
		i["latitude"] = FULL_HEIGHT/2 - float(i["latitude"][:-1]) * (-1 if i["latitude"][-1] == "S" else 1) / 180 * FULL_HEIGHT
		i["speed"] = float(i["speed"])

	# cropping and resizing ==============================================

	ZOOM = 3

	min_longitude = min(i["longitude"] for i in tracks)
	max_longitude = max(i["longitude"] for i in tracks)
	min_latitude = min(i["latitude"] for i in tracks)
	max_latitude = max(i["latitude"] for i in tracks)

	top = min_latitude - FULL_HEIGHT * 5/180
	left = min_longitude - FULL_WIDTH * 5/360
	bottom = max_latitude + FULL_HEIGHT * 5/180
	right = max_longitude + FULL_WIDTH * 5/360

	if right - left < FULL_HEIGHT*45/180:
		padding = (FULL_HEIGHT*45/180 - (right-left)) / 2
		right += padding
		left -= padding
	
	if right - left < bottom - top:
		padding = ((bottom-top) - (right-left)) / 2
		right += padding
		left -= padding

	if bottom - top < (right-left) / 1.618033988749894:
		padding = ((right-left) / 1.618033988749894 - (bottom-top)) / 2
		bottom += padding
		top -= padding

	if left < 0: left = 0
	if top < 0: top = 0
	if right > FULL_WIDTH: right = FULL_WIDTH
	if bottom > FULL_HEIGHT: bottom = FULL_HEIGHT


	new_map = map.crop((left, top, right, bottom))
	new_map = new_map.resize((round(new_map.size[0] * ZOOM), round(new_map.size[1] * ZOOM)))


	# drawing =============================================================	

	draw = ImageDraw.Draw(new_map)
	zoom_width, zoom_height = new_map.size

	sorted_tracks = {}
	for marker in tracks:
		marker["longitude"] = round((marker["longitude"] - left) * ZOOM)
		marker["latitude"] = round((marker["latitude"] - top) * ZOOM)
		if marker["name"] in sorted_tracks: sorted_tracks[marker["name"]].append(marker)
		else: sorted_tracks[marker["name"]] = [marker]

	for tracks in sorted_tracks.values():
		draw.line(
			[(marker["longitude"], marker["latitude"]) for marker in tracks],
			fill="white",
			width=round(DOT_SIZE/3)
		)

		current = ""
		for marker in tracks:
			if marker["stage"] != "" and current != marker["stage"]: current = marker["stage"]
			shape = get_shape(current)

			if shape == "triangle":
				triangle_coordinates = (
					marker["longitude"],
					marker["latitude"] - round(DOT_SIZE/2*ZOOM),
					marker["longitude"] - round(DOT_SIZE/2*ZOOM),
					marker["latitude"] + round(DOT_SIZE/2*ZOOM),
					marker["longitude"] + round(DOT_SIZE/2*ZOOM),
					marker["latitude"] + round(DOT_SIZE/2*ZOOM)
				)
				draw.polygon(triangle_coordinates, fill=get_colour(marker["speed"]))
				continue

			coordinates = (
				marker["longitude"] - round(DOT_SIZE/2*ZOOM),
				marker["latitude"] - round(DOT_SIZE/2*ZOOM),
				marker["longitude"] + round(DOT_SIZE/2*ZOOM),
				marker["latitude"] + round(DOT_SIZE/2*ZOOM)
			)
			if shape == "square": draw.rectangle(coordinates, fill=get_colour(marker["speed"]))
			elif shape == "circle": draw.ellipse(coordinates, fill=get_colour(marker["speed"]))

	return new_map.resize((zoom_width, zoom_height), resample=Image.ANTIALIAS) # anti aliasing


app = Flask(__name__)

@app.route("/")
def main():
	return render_template("index.html")


@app.route("/api/trackgen", methods=["POST"])
def gen_tracker():
	tracks = request.json

	if tracks == None: abort(400)	

	size = request.args.get("size", "small")

	make_map(tracks, size).save("tempFile.png")
	return send_file("tempFile.png")


@app.route("/api/hurdat", methods=["POST"])
def hurdat():
	data = request.json.split("\n")

	parsed = []
	unique_id = ""
	for line in data:
		cols = line.split(", ")
		if len(cols) == 3:
			unique_id = cols[0]
		else:
			parsed.append(
				{
					"name": unique_id,
					"latitude": cols[4],
					"longitude": cols[5],
					"speed": float(cols[6]),
					"stage": get_hurdat_stage(cols[3])
				}
			)
	
	make_map(parsed, "small").save("tempFile.png")
	return send_file("tempFile.png")


@app.route("/api/atcf",  methods=["POST"])
def atcf():	
	data = request.json.split("\n")

	parsed = []
	for line in data:
		cols = line.split(", ")
		parsed.append(
			{
				"name": cols[1],
				"latitude": cols[6][:-2]+"."+cols[6][-2:],
				"longitude": cols[7][:-2]+"."+cols[7][-2:],
				"speed": float(cols[8]),
				"stage": get_atcf_stage(cols[10])
			}
		)
	
	make_map(parsed, "small").save("tempFile.png")
	return send_file("tempFile.png")


@app.route("/api/ibtracs", methods=["POST"])
def ibtracs():
	data = request.json.split("\n")[2:]

	parsed = []
	for line in data:
		if line != "":
			cols = line.split(",")
			parsed.append(
				{
					"name": cols[0],
					"latitude": cols[8]+"N",
					"longitude": cols[9]+"E",
					"speed": sshs_to_speed(cols[25]),
					"stage": get_ibtracs_stage(cols[7])
				}
			)

	make_map(parsed, "small").save("tempFile.png")
	return send_file("tempFile.png")


@app.route("/api/rsmc", methods=["POST"])
def rsmc():	
	data = request.json.split("\n")


	unique_id = []
	parsed = []
	for line in data:
		cols = line.split(" ")
		cleaned_cols = []
		for col in cols:
			if col != "": cleaned_cols.append(col)
		cols = cleaned_cols
		if len(cols) == 9:
			unique_id = cols[1]
		else:
			parsed.append(
				{
					"name": unique_id,
					"latitude": cols[3][:-1]+"."+cols[3][-1:]+"N",
					"longitude": cols[4][:-1]+"."+cols[4][-1:]+"E",
					"speed": float(cols[6]),
					"stage": get_rsmc_stage(cols[2])
				}
			)

	make_map(parsed, "small").save("tempFile.png")
	return send_file("tempFile.png")



@app.route("/favicon.ico")
def favicon():
	return send_file("static/media/favicon.ico")


app.run("0.0.0.0")