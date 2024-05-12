# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.15.2
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# Run topic modeling for each year

# %%
# code generated by ChatGPT


import os
import math
import argparse
from bertopic import BERTopic
import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
from umap import UMAP
import seaborn as sns
import matplotlib.pyplot as plt
from collections import defaultdict
from sklearn.linear_model import LinearRegression
from .fit_dynamic_topic_model import load_data, get_embeddings


def load_model(min_cluster_size, n_neighbors, modeldir='models', 
               llm='gpt4', embedding='all-mpnet-base-v2') -> BERTopic:
    """
    Load model from pickle file

    Parameters
    ----------
    datadir : str
        Directory where data is stored
    min_cluster_size : int
        Minimum cluster size
    n_neighbors : int
        Number of neighbors

    Returns
    -------
    topic_model : BERTopic
        Topic model

    """

    model_name = f'model-bertopic_minclust-{min_cluster_size}_nneighbors-{n_neighbors}_{llm}'

    model_path = os.path.join(modeldir, model_name)
    if not os.path.exists(model_path):
        raise FileNotFoundError(f'Model {model_path} not found')

    embedding_model = SentenceTransformer(embedding)
    topic_model = BERTopic.load(model_path, embedding_model=embedding_model)
    print('Loaded model from %s' % os.path.join(model_path, model_name))
    return topic_model, embedding_model, model_name


def get_topics_over_time(sentences, years, topic_model, date_cutoff='2001-01-01'):
    print('getting topics over time')
    timestamps = [pd.to_datetime(f'{year}-01-01') for year in years]

    topics_over_time = topic_model.topics_over_time(sentences, timestamps)

    filter_date = pd.to_datetime(date_cutoff)
    topics_over_time = topics_over_time[topics_over_time['Timestamp'] > filter_date]

    # Calculate per-year probabilities by dividing each count by the sum of frequencies
    topics_over_time['Sum'] = topics_over_time.groupby('Timestamp')['Frequency'].transform('sum')
    topics_over_time['Probability'] = topics_over_time['Frequency'] / topics_over_time['Sum']

    return topics_over_time


def get_hierarchical_topics(topic_model, sentences, viz=False):
    hierarchical_topics = topic_model.hierarchical_topics(sentences)
    tree = topic_model.get_topic_tree(hierarchical_topics)
    if viz:
        fig = topic_model.visualize_hierarchy()
        if not os.path.exists('figures'):
            os.mkdir('figures')
        fig.write_html('figures/hierarchical_topics.html')
    return hierarchical_topics, tree


def plot_hierarchical_topics(topic_model, embeddings, sentences,
                             hierarchical_topics,
                             minclust, nneighbors,
                             save_embeddings=True,
                             umap_nneighbors=20):

    # Reduce dimensionality of embeddings, this step is optional
    reduced_embeddings = UMAP(n_neighbors=umap_nneighbors, 
                              n_components=2, 
                              min_dist=0.0, metric='cosine'
        ).fit_transform(embeddings)

    # Or, if you have reduced the original embeddings already:
    fig = topic_model.visualize_hierarchical_documents(
        sentences, hierarchical_topics, 
        reduced_embeddings=reduced_embeddings)

    if not os.path.exists('figures'):
        os.mkdir('figures')
    fig.write_html(f"figures/topic_viz_minclust-{minclust}_nneighbors-{nneighbors}.html")
    reduced_embeddings_df = pd.DataFrame(reduced_embeddings, columns=['C1', 'C2'])
    if save_embeddings:
        reduced_embeddings_df.to_csv(
            f"models/embedding-UMAP_minclust-{minclust}_nneighbors-{nneighbors}.csv",
            index=False)
    return fig, reduced_embeddings_df


def get_representative_docs(model_name, llm='gpt4'):
       # %%
    representative_docs = pd.read_csv(f'models/{model_name}'.replace('_{llm}', '_rep_docs.csv'))
    return representative_docs


def get_top_topics_over_time(topics_over_time, topic_model,
                             ntopics_to_plot=3,
                             filter_global_topic=True,
                             print_results=False):
    
    # get top 3 topics for each year, for plotting

    if filter_global_topic:
        topics_over_time_filt = topics_over_time.query("Topic > -1") # remove global topic
    else:
        topics_over_time_filt = topics_over_time

    
    top_topics = []
    for year in topics_over_time_filt.Timestamp.unique():
        year_data = topics_over_time_filt[topics_over_time_filt.Timestamp == year].sort_values(
            'Probability', ascending=False)
        if print_results:
            print(year)
            print(year_data[['Topic', 'Words', 'Probability']].head(
                ntopics_to_plot))
        top_topics.extend(year_data.Topic[:ntopics_to_plot].tolist())

    top_topics = list(set(top_topics))

    top_topics_over_time = topics_over_time[topics_over_time.Topic.isin(top_topics)]
    top_topics_over_time['Name'] = [
        topic_model.get_topic_info(i).Representation[0][0] for i in top_topics_over_time.Topic]

    return top_topics_over_time

def plot_top_topics(topics_over_time, topic_model, 
                    minclust, nneighbors,
                    top_n_topics=10,
                    ntopics_to_plot=3,
                    use_offsets=True, offset=None,
                    line_alpha=.5):
    # Get the top 3 topics for each year

    fig = topic_model.visualize_topics_over_time(topics_over_time, top_n_topics=10, 
                                        normalize_frequency=False, width=800)
    if not os.path.exists('figures'):
        os.mkdir('figures')
    fig.write_html(f'figures/topics_over_time_minclust-{minclust}_nneighbors-{nneighbors}.html')

    # plot timeseries with annotation

    top_topics_over_time = get_top_topics_over_time(topics_over_time, topic_model,
                                                    ntopics_to_plot=ntopics_to_plot)
    plt.figure(figsize=(10,5))
    sns.set_palette('colorblind')
    ax = sns.lineplot(x='Timestamp', y='Probability', hue='Name', 
                    data=top_topics_over_time, legend=False,
                    alpha=line_alpha)
    sns.despine()
    xlims = ax.get_xlim()
    ylims = [0, .08]
    #plt.ylim(ylims)

    # data from final year, for location of labels
    data_2022 = top_topics_over_time.query('Timestamp == "2022-01-01"')

        
    delta = 200 # spacing bw data and annotation

    xloc = ax.get_lines()[0].get_data()[0][-1] # location of 2022 data points on x axis
    xloc_2002 = ax.get_lines()[0].get_data()[0][0]

    # custom offsets to help avoid collisions between labels
    if offset is None:
        offset = defaultdict(lambda: 0)
        if use_offsets:
            offset[1] = -.0015
            offset[0] = .002
            offset[2] = -.002
            offset[13] = .0025
            offset[7] = -.002
            offset[5] = .001
            offset[19] = -.002

    # Plot line names to the right of each line
    for i in data_2022.index:
        topicnum = data_2022.loc[i, 'Topic']
        topicname = topic_model.get_topic_info(topicnum).Representation[0][0]
        probability = data_2022.loc[i, 'Probability']
        # allow tweaking of location
        probability_word = probability + offset[topicnum]
        plt.annotate(topicname, xy=(xloc, probability_word), 
                    xytext=(xloc + delta, probability_word), ha='left', va='center')
        plt.plot((xloc, xloc + delta), (probability, probability_word),
                color='k', alpha=0.5,linewidth=0.5)
    plt.tight_layout()
    if not os.path.exists('figures'):
        os.mkdir('figures')
    plt.savefig(f'figures/topics_over_time_minclust-{minclust}_nneighbors-{nneighbors}.png',
                dpi=300)


def get_slopes(top_topics_over_time, topic_model):
    slopes = {}
    for topic in top_topics_over_time.Topic.unique():
        topicdata = top_topics_over_time.query(f'Topic == {topic}')
        topicdata['year'] = [i.year for i in topicdata.Timestamp.tolist()]
        lr = LinearRegression()
        lr.fit(topicdata.year.values.reshape(-1, 1), topicdata.Probability)
        slopes[topic] = lr.coef_[0]

    # %%
    slope_df = pd.DataFrame({'topic': slopes.keys()})
    slope_df['slope'] = [slopes[topic] for topic in slope_df.topic]
    slope_df['topicname'] = [topic_model.get_topic_info(topic).Representation[0][0] for topic in slope_df.topic]
    slope_df = slope_df.sort_values('slope')
    return slope_df


# adapted from https://maartengr.github.io/BERTopic/api/plotting/hierarchical_documents.html#bertopic.plotting._hierarchical_documents.visualize_hierarchical_documents
def get_clustered_topics(topic_model, sentences, 
                         hierarchical_topics, reduced_embeddings, 
                         level_scale='linear', nr_levels=5):
  topic_per_doc = topic_model.topics_

  indices = []
  for topic in set(topic_per_doc):
      s = np.where(np.array(topic_per_doc) == topic)[0]
      size = len(s) if len(s) < 100 else int(len(s))
      indices.extend(np.random.choice(s, size=size, replace=False))
  indices = np.array(indices)

  df = pd.DataFrame({"topic": np.array(topic_per_doc)[indices]})
  df["doc"] = [sentences[index] for index in indices]
  df["topic"] = [topic_per_doc[index] for index in indices]


  # Combine data
  df["x"] = reduced_embeddings.C1
  df["y"] = reduced_embeddings.C2

  # Create topic list for each level, levels are created by calculating the distance
  distances = hierarchical_topics.Distance.to_list()
  if level_scale == 'log' or level_scale == 'logarithmic':
      log_indices = np.round(np.logspace(start=math.log(1,10), stop=math.log(len(distances)-1,10), num=nr_levels)).astype(int).tolist()
      log_indices.reverse()
      max_distances = [distances[i] for i in log_indices]
  elif level_scale == 'lin' or level_scale == 'linear':
      max_distances = [distances[indices[-1]] for indices in np.array_split(range(len(hierarchical_topics)), nr_levels)][::-1]
  else:
      raise ValueError("level_scale needs to be one of 'log' or 'linear'")

  for index, max_distance in enumerate(max_distances):

      # Get topics below `max_distance`
      mapping = {topic: topic for topic in df.topic.unique()}
      selection = hierarchical_topics.loc[hierarchical_topics.Distance <= max_distance, :]
      selection.Parent_ID = selection.Parent_ID.astype(int)
      selection = selection.sort_values("Parent_ID")

      for row in selection.iterrows():
          for topic in row[1].Topics:
              mapping[topic] = row[1].Parent_ID

      # Make sure the mappings are mapped 1:1
      mappings = [True for _ in mapping]
      while any(mappings):
          for i, (key, value) in enumerate(mapping.items()):
              if value in mapping.keys() and key != value:
                  mapping[key] = mapping[value]
              else:
                  mappings[i] = False

      # Create new column
      df[f"level_{index+1}"] = df.topic.map(mapping)
      df[f"level_{index+1}"] = df[f"level_{index+1}"].astype(int)
  return df



def plot_first_year():
        # plot only for first year - DEPRECATED

    plt.figure(figsize=(6,5))
    data_2002 = top_topics_over_time.query('Timestamp == "2002-01-01"')

    ax = sns.lineplot(x='Timestamp', y='Probability', hue='Name', 
                    data=top_topics_over_time, legend=False, alpha=0.1)

    plt.ylim(ylims)
    ax = sns.scatterplot(x='Timestamp', y='Probability', hue='Name', 
                    data=data_2002, legend=False)
    sns.despine()
    plt.xlim(xlims)

    delta = 200 # spacing bw data and annotation


    # Plot line names to the right of each line

    for i in data_2002.index:
        topicnum = data_2002.loc[i, 'Topic']
        topicname = topic_model.get_topic_info(topicnum).Representation[0][0]
        probability = data_2002.loc[i, 'Probability']
        # allow tweaking of location
        probability_word = probability
        if topicnum == 14:
            probability_word += .0015
        if topicnum == 5:
            probability_word += .003

        plt.annotate(topicname, xy=(xloc_2002, probability_word), xytext=(xloc_2002 + delta, probability_word), ha='left', va='center')
        plt.plot((xloc_2002, xloc_2002 + delta), (probability, probability_word), color='k', alpha=0.5,linewidth=0.5)
    plt.tight_layout()
    plt.savefig('topics_2002.png', dpi=300)

    # %%
    topics_over_time_extrapolated = data_2022
    import numpy as np
    np.random.seed(12345)

    def get_extrapolation(data_2022, extra_sd = 0.01):
        ntopics = len(data_2022.Topic.unique())
        extrapolation = {}

        timepoints = []
        probabilities = []
        topics = []
        names = []

        topic_mean_change = np.random.normal(loc=0, scale=0.005, size=ntopics)

        for i, topic in enumerate(data_2022.Topic.unique()):
            extrapolation[topic] = np.hstack(
                [data_2022.loc[data_2022.Topic == topic, 'Probability'],
                np.random.normal(loc=topic_mean_change[i], scale=extra_sd, size=10)])
            extrapolation[topic] = np.clip(np.cumsum(extrapolation[topic]), 
                                        a_max=None, a_min=0)


            for j, year in enumerate(range(2022, 2033)):
                timepoints.append(pd.to_datetime(f'{year}-01-01'))
                probabilities.append(extrapolation[topic][j])
                topics.append(topic)
                names.append(topic_model.get_topic_info(topic).Representation[0][0])


        extrap_df = pd.DataFrame(
            {'Topic': topics,
            'Timestamp': timepoints,
            'Probability': probabilities,
            'Name': names
            }, index=range(len(topics)))
        return(extrap_df)



    # %%
    # plot future extrapolation

    plt.figure(figsize=(8,5))
    ax = sns.lineplot(x='Timestamp', y='Probability', hue='Name', 
                    data=top_topics_over_time, 
                    legend=False)
    plt.ylim(ylims)
    n_extrap = 10
    for i in range(n_extrap):
        extrap_df = get_extrapolation(data_2022)
        ax = sns.lineplot(x='Timestamp', y='Probability', hue='Name', 
                        data=extrap_df, 
                        legend=False, alpha=0.2)

    sns.despine()
    xlims = ax.get_xlim()
    delta = 200 # spacing bw data and annotation

    xloc = ax.get_lines()[0].get_data()[0][-1] # location of 2022 data points on x axis
    xloc_2002 = ax.get_lines()[0].get_data()[0][0]

    plt.tight_layout()
    plt.savefig('topics_extrapolated.png', dpi=300)


if __name__ == '__main__':


    argparser = argparse.ArgumentParser()
    argparser.add_argument('--min_cluster_size', type=int, default=250)
    argparser.add_argument('--n_neighbors', type=int, default=50)
    argparser.add_argument('--datadir', type=str, default='data')
    argparser.add_argument('--modeldir', type=str, default='models')
    args = argparser.parse_args()

    # load the prefitted topic model, generated using fit_dynamic_topic_model.py

    use_gpt = True # use GPT-4 topic representations

    sentences, years = load_data(args.datadir)

    minclust, nneighbors = args.min_cluster_size, args.n_neighbors

    topic_model, embedding_model, model_name = load_model(minclust, nneighbors, args.modeldir)

    topics_over_time = get_topics_over_time(sentences, years, topic_model)

    hierarchical_topics, tree = get_hierarchical_topics(topic_model, sentences, viz=False)

    embeddings, embedding_model = get_embeddings(sentences)

    fig, reduced_embeddings = plot_hierarchical_topics(
        topic_model, embeddings, sentences, hierarchical_topics,
        args.min_cluster_size, args.n_neighbors)

    top_topics_over_time = get_top_topics_over_time(topics_over_time, topic_model)

    plot_top_topics(topics_over_time, topic_model, 
                    minclust, nneighbors)
    
    slope_df = get_slopes(top_topics_over_time, topic_model)
    slope_df.to_csv(f'models/{model_name}'.replace('_gpt4', '_slopes.csv'), index=False)    




    # %%
