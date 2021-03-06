from __future__ import print_function

"""
author: DI WU
stevenwudi@gmail.com
"""
import getopt
import sys
import dlib
# some configurations files for OBT experiments, originally, I would never do that this way of importing,
# it's simple way too ugly
from config import *
from scripts import *


class DSST_tracker():
    """
    http://blog.dlib.net/2015/02/dlib-1813-released.html
    Danelljan, Martin, et al. "Accurate scale estimation for robust visual tracking."
    Proceedings of the British Machine Vision Conference BMVC. 2014.
    """
    def __init__(self):
        self.name = 'DSST'
        self.type = 'rect'
        self.tracker = dlib.correlation_tracker()
        self.res = []
        self.feature_type = 'DSST_dlib'


def main(argv):
    trackers = [DSST_tracker()]
    #evalTypes = ['OPE', 'SRE', 'TRE']
    evalTypes = ['OPE']
    loadSeqs = 'TB50'
    try:
        opts, args = getopt.getopt(argv, "ht:e:s:", ["tracker=", "evaltype=", "sequence="])
    except getopt.GetoptError:
        print('usage : run_trackers.py -t <trackers> -s <sequences>' + '-e <evaltypes>')
        sys.exit(1)

    for opt, arg in opts:
        if opt == '-h':
            print('usage : run_trackers.py -t <trackers> -s <sequences>' + '-e <evaltypes>')
            sys.exit(0)
        elif opt in ("-t", "--tracker"):
            trackers = [x.strip() for x in arg.split(',')]
            # trackers = [arg]
        elif opt in ("-s", "--sequence"):
            loadSeqs = arg
            if loadSeqs != 'All' and loadSeqs != 'all' and \
                            loadSeqs != 'tb50' and loadSeqs != 'tb100' and \
                            loadSeqs != 'cvpr13':
                loadSeqs = [x.strip() for x in arg.split(',')]
        elif opt in ("-e", "--evaltype"):
            evalTypes = [x.strip() for x in arg.split(',')]

    if SETUP_SEQ:
        print('Setup sequences ...')
        butil.setup_seqs(loadSeqs)

    print('Starting benchmark for {0} trackers, evalTypes : {1}'.format(
        len(trackers), evalTypes))
    for evalType in evalTypes:
        seqNames = butil.get_seq_names(loadSeqs)
        seqs = butil.load_seq_configs(seqNames)
        ######################################################################
        trackerResults = run_trackers(trackers, seqs, evalType, shiftTypeSet)
        ######################################################################
        for tracker in trackers:
            results = trackerResults[tracker]
            if len(results) > 0:
                ######################################################################
                evalResults, attrList = butil.calc_result(tracker, seqs, results, evalType)
                ######################################################################
                print ("Result of Sequences\t -- '{0}'".format(tracker.name))
                for seq in seqs:
                    try:
                        print('\t{0} {1} \taveCoverage : {2:0.2f}, \taveErrCenter : {3:0.2f}'.format(seq.name,
                              " " * (12 - len(seq.name)), sum(seq.aveCoverage) / len(seq.aveCoverage) * 100,
                              sum(seq.aveErrCenter) / len(seq.aveErrCenter)))
                    except:
                        print('\t\'{0}\'  ERROR!!'.format(seq.name))

                print("Result of attributes\t -- '{0}'".format(tracker.name))
                for attr in attrList:
                    print("\t {0}, \t overlap : {1:.1f}, \t failures : {2:.1f}".format(attr.name, attr.overlap, attr.error))

                if SAVE_RESULT:
                    butil.save_scores(attrList)


def run_trackers(trackers, seqs, evalType, shiftTypeSet):
    tmpRes_path = RESULT_SRC.format('tmp/{0}/'.format(evalType))
    if not os.path.exists(tmpRes_path):
        os.makedirs(tmpRes_path)

    numSeq = len(seqs)

    trackerResults = dict((t, list()) for t in trackers)
    ##################################################
    # chose sequence to run from below
    ##################################################
    for idxSeq in range(0, numSeq):
        s = seqs[idxSeq]
        subSeqs, subAnno = butil.get_sub_seqs(s, 20.0, evalType)

        for idxTrk in range(len(trackers)):
            t = trackers[idxTrk]

            if not OVERWRITE_RESULT:

                trk_src = os.path.join(RESULT_SRC.format(evalType), t.name)
                result_src = os.path.join(trk_src, s.name + '.json')
                if os.path.exists(result_src):
                    seqResults = butil.load_seq_result(evalType, t, s.name)
                    seqResults[0].resType = 'rect'
                    trackerResults[t].append(seqResults)
                    continue
            seqResults = []
            seqLen = len(subSeqs)
            for idx in range(seqLen):
                print('{0}_{1}, {2}_{3}:{4}/{5} - {6}'.format(
                    idxTrk + 1, t.feature_type, idxSeq + 1, s.name, idx + 1, seqLen, evalType))
                rp = tmpRes_path + '_' + t.feature_type + '_' + str(idx + 1) + '/'
                if SAVE_IMAGE and not os.path.exists(rp):
                    os.makedirs(rp)
                subS = subSeqs[idx]
                subS.name = s.name + '_' + str(idx)

                ####################
                t, res = run_KCF_variant(t, subS, debug=True)
                ####################
                if evalType == 'SRE':
                    r = Result(t.name, s.name, subS.startFrame, subS.endFrame,
                               res['type'], evalType, res['res'], res['fps'], shiftTypeSet[idx])
                else:
                    r = Result(t.name, s.name, subS.startFrame, subS.endFrame,
                               res['type'], evalType, res['res'], res['fps'], None)
                try:
                    r.tmplsize = res['tmplsize'][0]
                except:
                    pass
                r.refresh_dict()
                seqResults.append(r)
            # end for subseqs
            if SAVE_RESULT:
                butil.save_seq_result(seqResults)

            trackerResults[t].append(seqResults)
            # end for tracker
    # end for allseqs
    return trackerResults


def run_KCF_variant(tracker, seq, debug=False):
    import cv2
    import matplotlib.pyplot as plt

    start_time = time.time()
    tracker.res = []
    if debug:
        win = dlib.image_window()

    for frame in range(seq.endFrame - seq.startFrame+1):
        image_filename = seq.s_frames[frame]
        image_path = os.path.join(seq.path, image_filename)
        img_rgb = cv2.imread(image_path)
        img_rgb = img_rgb[:, :, ::-1]
        if frame == 0:
            rect = seq.gtRect[0]
            gtRect = dlib.rectangle(rect[0], rect[1], rect[0] + rect[2], rect[1] + rect[3])
            tracker.tracker.start_track(img_rgb, gtRect)
            tracker.res.append([gtRect.left(), gtRect.top(), gtRect.width(), gtRect.height()])
        else:
            tracker.tracker.update(img_rgb)
            rect = tracker.tracker.get_position()
            tracker.res.append([rect.left(), rect.top(), rect.width(), rect.height()])

        if debug and frame > 0:
            print("Frame ==", frame)
            print("pos", np.array(tracker.res[-1]).astype(int))
            print("gt", seq.gtRect[frame])
            print("\n")
            win.clear_overlay()
            win.set_image(img_rgb)
            win.add_overlay(tracker.tracker.get_position())
            #plt.waitforbuttonpress(0.1)

    total_time = time.time() - start_time
    tracker.fps = len(tracker.res) / total_time
    print("Frames-per-second:", tracker.fps)

    res = {'type': 'rect', 'res': tracker.res, 'fps': tracker.fps}

    return tracker, res

if __name__ == "__main__":
    main(sys.argv[1:])
