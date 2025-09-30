import os
import csv
current_file_directory = os.path.dirname(os.path.abspath(__file__))
csv_directory = os.path.join(current_file_directory, "Candidate solutions.csv")
NUM_END = 10
def get_candidate_list():
    result = []
    with open(csv_directory, mode="r") as file:
        # Candidates are stored in a CSV file. Read the CSV
        csv_reader = csv.reader(file)
        
        # Convert CSV rows

        for row in csv_reader:
            result += row
    return result[1:]

# Add new candidates top the CSV file
def add_candidate(compositionID):
    with open(csv_directory, mode='a', newline='') as file:
        csv_writer = csv.writer(file)
        csv_writer.writerow([compositionID])