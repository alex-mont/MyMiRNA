from commons import main_branch
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from mirbase_scraper import get_accession_number, get_details
from my_mirna import cutadapt, fastqc, mapping_shortstack, multiqc, structure
from target_scan_scraper import target_scan_get_table
import os
import re
import RNA

app = Flask(__name__)
CORS(app)


@app.route('/trimming', methods=['POST'])
def quality_and_trimming():
    return "assets/multiqc_report.html"
    params = request.get_json(silent=True, cache=False)

    adapter = params["adapter"]

    quality = params["qual"]

    index = str(params["index"])

    # TODO retrieve cores from request
    cores = 8

    fastqc_folder = index + "/fastqc"
    trimmed_folder = index + "/trimmed"
    output_folder = "gui/src/assets/"

    input_data_folder = "data"

    filenames = os.listdir(input_data_folder)

    # Creates folders to store the fastqc output file and the trimmed fastq files
    os.mkdir(index)
    os.mkdir(fastqc_folder)
    os.mkdir(trimmed_folder)
    os.mkdir(output_folder)

    # First fastqc run
    for filename in filenames:
        fastqc(input_data_folder + "/" + filename, fastqc_folder)

    # The adapter is trimmed and the file are saved as original_name_trimmed.fastq
    trimmed_filenames = []
    for filename in filenames:
        trimmed_filename = re.sub(r'\.fastq', '', filename) + "Trimmed.fastq"
        trimmed_filenames.append(trimmed_filename)
        cutadapt(input_data_folder + "/" + filename, trimmed_folder+"/"+trimmed_filename, adapter, quality, cores)

    # Second fastqc run
    for filename in trimmed_filenames:
        fastqc(trimmed_folder+"/"+filename, fastqc_folder)

    # All the fastqc results are reported in a single multiqc file
    multiqc(fastqc_folder, output_folder)

    return "assets/multiqc_report.html"


@app.route("/shortstack", methods=['POST'])
def shortstack_mapping():
    return "assets/shortstack.html"
    params = request.get_json(silent=True, cache=False)

    multimap_threshold = params['multimap']

    n_cores = params['cores']

    index = str(params["index"])

    # Creates a folder for the shortstack output file
    base_dir = index+"/shortstack"
    os.mkdir(base_dir)

    # Maps each trimmed file in the trimmed folder and converts the bam output to fastq
    shortstack_dirs = []
    for filename in os.listdir(index+"/trimmed"):
        tmp = re.sub(r'\.fastq', '', filename)
        tmp_dir = base_dir+"/"+tmp
        shortstack_dirs.append(tmp_dir)
        mapping_shortstack(index+"/trimmed/"+filename,
                           "assets/human_index/genome.fa",
                           tmp_dir, multimap_threshold,
                           n_cores)

    # Exports data about the mapping
    template_parameters = []

    for log_dir in shortstack_dirs:
        with open(log_dir+"/Log.txt") as file:
            text = file.read()
            name = log_dir.split('/')[-1]
            values = []

            match = re.search(r'Unique mappers: ([0-9]{5,} / [0-9]{5,}) \(([0-9]{,3}\.[0-9] %)\)', text)
            if match is None:
                values.append(("Unique mappers", "None", "None"))
            else:
                values.append(("Unique mappers", match.group(1), match.group(2)))

            match = re.search(r'Multi mappers: ([0-9]{5,} / [0-9]{5,}) \(([0-9]{,3}\.[0-9] %)\)', text)
            if match is None:
                values.append(("Multi mappers", "None", "None"))
            else:
                values.append(("Multi mappers", match.group(1), match.group(2)))

            match = re.search(r'Multi mappers ignored and marked as unmapped: ([0-9]{5,} / [0-9]{5,}) \(([0-9]{,3}\.[0-9] %)\)', text)
            if match is None:
                values.append(("Multi mappers ignored and marked as unmapped", "None", "None"))
            else:
                values.append(("Multi mappers ignored and marked as unmapped", match.group(1), match.group(2)))

            match = re.search(r'Non mappers: ([0-9]{5,} / [0-9]{5,}) \(([0-9]{,3}\.[0-9] %)\)', text)
            if match is None:
                values.append(("Non mappers", "None", "None"))
            else:
                values.append(("Non mappers", match.group(1), match.group(2)))
        template_parameters.append((name, values))

    rendered = render_template("shortstack.html", params=template_parameters)

    with open("gui/src/assets/shortstack.html".format(index), 'w') as file:
        file.write(rendered)

    return "assets/shortstack.html"


@app.route("/mirna", methods=['POST'])
def mirna():
    params = request.get_json(silent=True, cache=False)

    index = str(params["index"])

    return main_branch("mirna", index, params)


@app.route("/mirnas", methods=['GET'])
def mirnas():

    index = str(request.args.get("index"))

    with open(index+"/mirna/mirna.names") as mirna_names_file:
        mirna_names = [re.sub(r'\n', '', name) for name in mirna_names_file.readlines()]

    ret = {
        "mature": [],
        "pre": []
    }

    for name in mirna_names:
        if re.search(r'^[a-zA-Z]{2,3}-[a-zA-Z]{2,3}-[0-9]{3,5}$', name) is None:
            ret["mature"].append(name)
        else:
            ret["pre"].append(name)

    return jsonify(ret)


@app.route("/mirnas/<string:mirna_name>", methods=['GET'])
def get_mirna(mirna_name):

    index = str(request.args.get("index"))

    accession = get_accession_number(mirna_name)

    params = get_details(mirna_name, accession)

    target_table = target_scan_get_table(mirna_name)

    dot_bracket, _ = RNA.fold(params["sequence"])

    structure(params["sequence"], dot_bracket, mirna_name, index)

    params["img"] = mirna_name + ".png"

    rendered = render_template("mirnadetail.html", param=params, table=target_table)

    with open("gui/src/assets/mirnadetail.html".format(index), 'w') as file:
        file.write(rendered)

    return "assets/mirnadetail.html".format(index)


@app.route("/pirna", methods=['POST'])
def pirna():
    params = request.get_json(silent=True, cache=False)

    index = str(params["index"])

    return main_branch("pirna", index, params)


@app.route("/ncrna", methods=['POST'])
def sncrna():
    params = request.get_json(silent=True, cache=False)

    index = str(params["index"])

    return main_branch("sncrna", index, params)


if __name__ == "__main__":
    app.run('127.0.0.1', 8080)
