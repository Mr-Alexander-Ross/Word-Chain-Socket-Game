def get_top_5():
    with open("WordChainRecords.txt") as f:
        document = f.readlines()
        # Sorts document by # of rounds
        sorted_document = sorted(document, key=lambda x: int(x.split(',')[3]),reverse=True)
        output = 'High Scores: \n'
        for i,entry in enumerate(sorted_document[:5]):
            output += f'{i+1}. {entry.split(',')[0]} \t Score:{entry.split(',')[3]}'
        return output
print("Goodbye\n" + get_top_5())